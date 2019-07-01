# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CalvingFrontMachine
								 A QGIS plugin
 Generates polygonal calving front/land-ocean vector masks from raster images.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
							  -------------------
		begin				: 2018-07-24
		git sha			  : $Format:%H$
		copyright			: (C) 2018 by Daniel Cheng
		email				: dlcheng@uci.edu
 ***************************************************************************/

/***************************************************************************
 *																		 *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or	 *
 *   (at your option) any later version.								   *
 *																		 *
 ***************************************************************************/
"""
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import QAction
from qgis.core import *

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .calving_front_machine_dialog import CalvingFrontMachineDialog
from .calving_front_machine_processing import layerSubsetSave, layerSubsetLoad, layerWarp, layerResize
import os, shutil, glob, subprocess
import numpy as np

class CalvingFrontMachine:
	"""QGIS Plugin Implementation."""
	
	def __init__(self, iface):
		"""Constructor.
		
		:param iface: An interface instance that will be passed to this class
			which provides the hook by which you can manipulate the QGIS
			application at run time.
		:type iface: QgsInterface
		"""
		# Save reference to the QGIS interface
		self.iface = iface
		# initialize plugin directory
		self.plugin_dir = os.path.dirname(__file__)
		# initialize locale
		locale = QSettings().value('locale/userLocale')[0:2]
		locale_path = os.path.join(
			self.plugin_dir,
			'i18n',
			'CalvingFrontMachine_{}.qm'.format(locale))
		
		if os.path.exists(locale_path):
			self.translator = QTranslator()
			self.translator.load(locale_path)
			
			if qVersion() > '4.3.3':
				QCoreApplication.installTranslator(self.translator)
		
		# Create the dialog (after translation) and keep reference
		self.dlg = CalvingFrontMachineDialog()
		
		# Declare instance attributes
		self.actions = []
		self.menu = self.tr(u'&Calving Front Machine')
		# TODO: We are going to let the user set this up in a future iteration
		self.toolbar = self.iface.addToolBar(u'CalvingFrontMachine')
		self.toolbar.setObjectName(u'CalvingFrontMachine')
	
	# noinspection PyMethodMayBeStatic
	def tr(self, message):
		"""Get the translation for a string using Qt translation API.
		
		We implement this ourselves since we do not inherit QObject.
		
		:param message: String for translation.
		:type message: str, QString
		
		:returns: Translated version of message.
		:rtype: QString
		"""
		# noinspection PyTypeChecker,PyArgumentList,PyCallByClass
		return QCoreApplication.translate('CalvingFrontMachine', message)
	
	def add_action(
		self,
		icon_path,
		text,
		callback,
		enabled_flag=True,
		add_to_menu=True,
		add_to_toolbar=True,
		status_tip=None,
		whats_this=None,
		parent=None):
		"""Add a toolbar icon to the toolbar.
		
		:param icon_path: Path to the icon for this action. Can be a resource
			path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
		:type icon_path: str
		
		:param text: Text that should be shown in menu items for this action.
		:type text: str
		
		:param callback: Function to be called when the action is triggered.
		:type callback: function
		
		:param enabled_flag: A flag indicating if the action should be enabled
			by default. Defaults to True.
		:type enabled_flag: bool
		
		:param add_to_menu: Flag indicating whether the action should also
			be added to the menu. Defaults to True.
		:type add_to_menu: bool
		
		:param add_to_toolbar: Flag indicating whether the action should also
			be added to the toolbar. Defaults to True.
		:type add_to_toolbar: bool
		
		:param status_tip: Optional text to show in a popup when mouse pointer
			hovers over the action.
		:type status_tip: str
		
		:param parent: Parent widget for the new action. Defaults None.
		:type parent: QWidget
		
		:param whats_this: Optional text to show in the status bar when the
			mouse pointer hovers over the action.
		
		:returns: The action that was created. Note that the action is also
			added to self.actions list.
		:rtype: QAction
		"""
		
		icon = QIcon(icon_path)
		action = QAction(icon, text, parent)
		action.triggered.connect(callback)
		action.setEnabled(enabled_flag)
		
		if status_tip is not None:
			action.setStatusTip(status_tip)
		
		if whats_this is not None:
			action.setWhatsThis(whats_this)
		
		if add_to_toolbar:
			self.toolbar.addAction(action)
		
		if add_to_menu:
			self.iface.addPluginToMenu(
				self.menu,
				action)
		
		self.actions.append(action)
		
		return action
	
	def initGui(self):
		"""Create the menu entries and toolbar icons inside the QGIS GUI."""
	
		icon_path = ':/plugins/calving_front_machine/icon.png'
		self.add_action(
			icon_path,
			text=self.tr(u'Mask calving fronts/land-ocean.'),
			callback=self.run,
			parent=self.iface.mainWindow())
	
	def unload(self):
		"""Removes the plugin menu item and icon from QGIS GUI."""
		for action in self.actions:
			self.iface.removePluginMenu(
				self.tr(u'&Calving Front Machine'),
				action)
			self.iface.removeToolBarIcon(action)
		# remove the toolbar
		del self.toolbar
		
	def findGroups(self, root:QgsLayerTree):
		"""Return a string list of groups."""
		result = []
		for child in root.children():
			if isinstance(child, QgsLayerTreeGroup):
				result.append(child.name())
				result.extend(self.findGroups(child))
		return result
	
	def perform_subsetting(self, rasterLayers, rasterPrefix, domainLayer, rasterGroup):
		print('Performing subsetting...')
		
		#Make directories if not already existing
		raw_path = self.resolve('landsat_raw/' + domainLayer.name())
		mask_path = self.resolve('landsat_preds/' + domainLayer.name())
		if not os.path.exists(raw_path):
			os.mkdir(raw_path)
		if not os.path.exists(mask_path):
			os.mkdir(mask_path)
		
		# Clear data from any previous runs
		files = glob.glob(raw_path + '/*')
		for f in files:
			if os.path.isfile(f):
				os.remove(f)
		files = glob.glob(mask_path + '/*')
		for f in files:
			if os.path.isfile(f):
				os.remove(f)
		
		# Perform subsetting for each layer
		count = 0
		resolutions = []
		for rasterLayer in rasterLayers:
			if rasterLayer.name()[-2:] in rasterPrefix:
				print(rasterLayer.layer().source())
				rasterLayer = layerWarp(rasterLayer, domainLayer)
				resolution = layerSubsetSave(rasterLayer, domainLayer, rasterGroup, domainLayer.name() + "_" + rasterLayer.name())
				resolutions.append(resolution)
				count += 1
		
		# Resize the images to the median size to account for reprojection differences
		count = 0
		resolution = np.median(resolutions, axis=0)
		print('Resizing subsets to', resolution)
		rasterLayers = rasterGroup.findLayers()
		for rasterLayer in rasterLayers:
			if rasterLayer.name()[-2:] in rasterPrefix:
				layerResize(rasterLayer.layer(), domainLayer, domainLayer.name() + "_" + str(count), resolution)
				count += 1
	
	def perform_saving(self, rasterLayers, rasterPrefix, domainLayer):		
		count = 0
		#Save for training
		source_path_base = self.resolve('landsat_raw/' + domainLayer.name())
		dest_path_base = r'D:/Daniel/Documents/GitHub/ultrasound-nerve-segmentation/landsat_raw/train_full/' + domainLayer.name()
		if not os.path.exists(dest_path_base):
			os.mkdir(dest_path_base)
		for rasterLayer in rasterLayers:
			if rasterLayer.name()[-2:] in rasterPrefix:
				name = domainLayer.name() + "_" + str(count) + '.png'
				source_path = os.path.join(source_path_base, name)
				dest_path = os.path.join(dest_path_base, name)
				shutil.copy2(source_path, dest_path)
				count += 1
				# imsave(path + name + '.png', img)
	
	def processLayers(self, domainLayerName, check_masking, check_saving, check_postprocessing):
		print('Performing masking...')
		launchcommand = r'C:\Users\Daniel\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\calvingfrontmachine\cfm.bat'
		check_masking = str(int(check_masking))
		check_postprocessing = str(int(check_postprocessing))
		check_saving = str(int(check_saving))
		arguments = [launchcommand, domainLayerName, check_masking, check_saving, check_postprocessing]
		print(arguments)
		p = subprocess.Popen(arguments, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_CONSOLE)
		while True:
			line = p.stdout.readline()
			print(str(line))
			if p.poll() != None:
				print('exit code: ', p.poll())
				break
		p.kill()
		
	def resolve(self, name, basepath=None):
		if not basepath:
		  basepath = os.path.dirname(os.path.realpath(__file__))
		return os.path.join(basepath, name)
	
	def run(self):
		"""Run method that performs all the real work"""
		# Load layer selection dropdown options
		project = QgsProject.instance()
		root = project.layerTreeRoot()
		layers = [node.layer() for node in root.findLayers()]
		domain_layer_list = []
		for layer in layers:
			if layer.type() == QgsMapLayer.VectorLayer:
				domain_layer_list.append(layer.name())
		# Load prefix selection dropdown options
		raster_prefix_list = ['B5', 'B4']
		# Load group selection dropdown options
		groups = self.findGroups(root)
		
		# Clear previous selection options
		self.dlg.comboBox_rasterPrefix.clear()
		self.dlg.comboBox_rasterGroup.clear()
		self.dlg.comboBox_domainLayer.clear()
		self.dlg.comboBox_rasterPrefix.addItems(raster_prefix_list)
		self.dlg.comboBox_rasterGroup.addItems(groups)
		self.dlg.comboBox_domainLayer.addItems(domain_layer_list)
		
		# show the dialog
		self.dlg.show()
		# Run the dialog event loop
		result = self.dlg.exec_()
		# See if OK was pressed
		if result:
			# Check options
			check_subsetting = self.dlg.checkBox_subsetting.isChecked()				#Whether or not to perform subsetting of the raster images from the domain
			check_masking = self.dlg.checkBox_masking.isChecked()					#Performs masking using the neural net
			check_postprocessing = self.dlg.checkBox_postprocessing.isChecked()		#Performs postprocessing on image masks
			check_saving = self.dlg.checkBox_saving.isChecked()						#Saves image raws/masks for training the neural net
			check_vectorization = self.dlg.checkBox_vectorization.isChecked()		#Performs vectorization/smoothing
			check_adding = self.dlg.checkBox_adding.isChecked()						#Adds the results to the project
			
			# Get selection indices
			rasterPrefixIndex = self.dlg.comboBox_rasterPrefix.currentIndex()
			rasterGroupIndex = self.dlg.comboBox_rasterGroup.currentIndex()
			domainLayerIndex = self.dlg.comboBox_domainLayer.currentIndex()
			
			# Get string values corresponding to selection indices
			rasterPrefix = ['B5', 'B4', 'B7']
			rasterGroupName = groups[rasterGroupIndex]
			domainGroupName = domain_layer_list[domainLayerIndex]
			
			# Get layer objects based on selection string values
			rasterGroup = root.findGroup(rasterGroupName)
			rasterLayers = rasterGroup.findLayers()
			for layer in QgsProject.instance().mapLayers().values():
				if layer.name() == domainLayerName:
					domainLayer = layer
					break
					
			# Get layer objects based on selection string values
			if (domainGroup
			domainGroup = root.findGroup(domainGroupName)
			domainLayers = domainGroup.findLayers()
			for layer in QgsProject.instance().mapLayers().values():
				if layer.name() == domainLayerName:
					domainLayer = layer
					break
					
            
			#Save subsets of raster source files using clipping domain
			if check_subsetting:
				self.perform_subsetting(rasterLayers, rasterPrefix, domainLayer, rasterGroup)
			
			#Optionally, save subsets for training
			if check_saving:
				self.perform_saving(rasterLayers, rasterPrefix, domainLayer)
				
			#Run Neural Net and perform masking/postprocessing/additional training data saving
			if check_masking or check_postprocessing or check_saving:
				self.processLayers(domainLayer.name(), check_masking, check_saving, check_postprocessing)
			
			#Vectorize masks and add vector layers to project
			count = 0
			for rasterLayer in rasterLayers:
				try:
					if rasterLayer.name()[-2:] in rasterPrefix:
						if check_vectorization:
							lineLayer, polygonLayer = layerSubsetLoad(rasterLayer.layer(), domainLayer, rasterGroup, domainLayer.name() + "_" + str(count))
							if check_adding:
								# step 1: add the layer to the registry, False indicates not to add to the layer tree
								QgsProject.instance().addMapLayer(lineLayer, False)
								QgsProject.instance().addMapLayer(polygonLayer, False)
								# step 2: append layer to the root group node
								rasterLayer.parent().insertLayer(0, lineLayer)
								rasterLayer.parent().insertLayer(0, polygonLayer)
								# step 3: Add transparency slider to polygon layers
								#polygonLayer.setCustomProperty("embeddedWidgets/count", 1)
								#polygonLayer.setCustomProperty("embeddedWidgets/0/id", "transparency")
								# Alter fill style for vector layers
								polygonSymbol = polygonLayer.renderer().symbol()
								lineSymbol = lineLayer.renderer().symbol()
								polygonSymbol.setColor(lineSymbol.color())
								polygonSymbol.setOpacity(0.25)
								# Redraw canvas and save variable to global context
								self.iface.layerTreeView().refreshLayerSymbology(lineLayer.id())
								self.iface.layerTreeView().refreshLayerSymbology(polygonLayer.id())
							count += 1
				except Exception as e:
					print(e)
