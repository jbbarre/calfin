from osgeo import gdal,ogr,osr
import os

#def preproc_lsat(filen):
ProjectPath=
#Clipping shapefile to domain boundaries{{{
shpDomain=ProjectPath+'/DATA_REPOSITORY/BOXES/'+DomainName+'.shp'
dom=fiona.open(shpDomain,'r')
nproj=np.float(dom.crs['init'][5:9])
spacing=50
interp='cubic'
gdalwarp='gdalwarp'
subsetsizex='256'
subsetsizey='256'
#WARNING PATH TO GDAL
os.system(gdalwarp+' -cutline '+shpDomain+' -crop_to_cutline '+filen+' -tr '+spacing+' '+spacing+' -r '+interp+' '+ProjectPath+'/'+filen.split('.tif')[0]+'_crop.tif')
#}}}
#Rescale subset{{{
os.system(gdalwarp+' -ts '+subsetsizex+' '+subsetsizey+' '+filen.split('.tif')[0]+'_crop.tif '+' '+filen.split('.tif')[0]+'_subset.tif')
#}}}
#reading tif file{{{
a=gdal.Open(ProjectPath+'/'+file.split('.tif')[0]+'_crop.tif')
b=a.GetRasterBand(1)
raw=b.ReadAsArray()
#}}}
#Shadow-highlight enhancement{{{

#}}}

