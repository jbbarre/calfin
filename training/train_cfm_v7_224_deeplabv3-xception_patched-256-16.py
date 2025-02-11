import numpy as np
import matplotlib.pyplot as plt
from keras.models import Model, Input
from keras.layers import Concatenate, Conv2D, MaxPooling2D, Conv2DTranspose, Dropout, UpSampling2D, BatchNormalization, RepeatVector, Reshape, Permute, Flatten
from keras.optimizers import Adam
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau, EarlyStopping
from keras.activations import relu, sigmoid
from keras.regularizers import l1, l2, l1_l2
from keras.layers import Activation
from keras import backend as K
from segmentation_models.losses import bce_jaccard_loss, jaccard_loss, binary_crossentropy
from segmentation_models.metrics import iou_score, jaccard_score

import sys
sys.path.insert(0, 'keras-deeplab-v3-plus')
from model_cfm import Deeplabv3, _xception_block
from clr_callback import CyclicLR
from AdamAccumulate import AdamAccumulate

import os
os.environ["CUDA_VISIBLE_DEVICES"]="0"

import cv2, glob
from skimage.io import imsave, imread
from skimage.transform import resize, rotate, rescale
from random import shuffle

from data_cfm_patched import load_validation_data
from albumentations import *
from aug_generators import aug_daniel, imgaug_generator_patched

full_size = 256
img_size = 224
stride = 16
data_path = 'data/'
pred_path = 'preds/'
temp_path = 'temp/'
K.set_image_data_format('channels_last')  # TF dimension ordering in this code

if __name__ == '__main__':
	print('-'*30)
	print('Loading validation data...')
	print('-'*30)
	validation_data = load_validation_data(full_size, img_size, stride) 
	
	model_checkpoint = ModelCheckpoint('cfm_weights_patched_no_sce_' + str(img_size) + '_e{epoch:02d}_iou{val_iou_score:.4f}.h5', monitor='val_iou_score', save_best_only=False)
	clr_triangular = CyclicLR(mode='triangular2', step_size=12000, base_lr=6e-5, max_lr=6e-4)
	callbacks_list = [
		#EarlyStopping(patience=6, verbose=1, restore_best_weights=False),
		#clr_triangular,
		model_checkpoint
	]
	
	SMOOTH = 1e-12
	def bce_ln_jaccard_loss(gt, pr, bce_weight=1.0, smooth=SMOOTH, per_image=True):
		bce = K.mean(binary_crossentropy(gt, pr))
		loss = bce_weight * bce - K.log(jaccard_score(gt, pr, smooth=smooth, per_image=per_image))
		return loss
	
	def ln_iou_score(gt, pr, bce_weight=1.0, smooth=SMOOTH, per_image=True):
		score = -K.log(iou_score(gt, pr, smooth=smooth, per_image=per_image))
		return score
	
	print('-'*30)
	print('Creating and compiling model...')
	print('-'*30)
	img_shape = (img_size, img_size, 3)
	inputs = Input(shape=img_shape)
	model = Deeplabv3(input_shape=(img_size, img_size,3), classes=16, OS=16, backbone='xception', weights=None)
	
	model.compile(optimizer=AdamAccumulate(lr=1e-4, accum_iters=4), loss=bce_ln_jaccard_loss, metrics=['binary_crossentropy', iou_score, 'accuracy'])
	model.summary()
	model.load_weights('cfm_weights_patched_224_e03_iou0.4676.h5')
	
	print('-'*30)
	print('Fitting model...')
	print('-'*30)
	train_generator = imgaug_generator_patched(4, img_size=full_size, patch_size=img_size, patch_stride=stride)
	history = model.fit_generator(train_generator,
				steps_per_epoch=16000,
				epochs=80,
				validation_data=validation_data,
				verbose=1,
#				max_queue_size=64,
#				use_multiprocessing=True,
#				workers=2,
				callbacks=callbacks_list)
	print(history.history)
