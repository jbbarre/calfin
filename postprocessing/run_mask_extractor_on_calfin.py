import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from keras import backend as K
K.set_image_data_format('channels_last')  # TF dimension ordering in this code

#ignore low contrast warnings
import warnings
warnings.filterwarnings("ignore")

import sys, glob, cv2, os, datetime
sys.path.insert(1, '../training/keras-deeplab-v3-plus')
sys.path.insert(2, '../training')

from validation import print_calfin_domain_metrics, print_calfin_all_metrics, output_calendar_csv
from preprocessing import preprocess
from processing import process, compile_model
from postprocessing import postprocess

def main(settings, metrics):
    #Begin processing validation images
#    troubled_ones = [3, 14, 22, 43, 66, 83, 97, 114, 161]
#    troubled_ones = [0, 4]
    troubled_ones = [16]
    domains = ['Qeqertarsuup', 'Kakiffaat', 'Nunatakavsaup', 'Alangorssup', 'Akullikassaap', 'Upernavik-NE', 'Upernavik-NW',
               'Upernavik-SE', 'Sermikassak-N', 'Sermikassak-S', 'Inngia', 'Umiammakku', 'Rink-Isbrae', 'Kangerlussuup', 
               'Kangerdluarssup', 'Perlerfiup', 'Sermeq-Silarleq', 'Kangilleq', 'Sermilik', 'Lille', 'Store']
    domains = ['Akullikassaap']
    
    
#    for i in range(95, 96):
#    for i in troubled_ones:
    
#    for i in range(617, len(settings['validation_files'])):
#    for i in range(617, 1208):
    for i in range(0, int(len(settings['validation_files'])/2)):
        
#        if 'Rink-Isbrae' in settings['validation_files'][i]:
#        if 'Upernavik-NE' in settings['validation_files'][i]:
#        if i % 10 != 0:
#        if 'Upernavik' in settings['validation_files'][i] or 'Umiammakku' in settings['validation_files'][i] or 'Inngia' in settings['validation_files'][i]:
#        if '2005-05-09' in settings['validation_files'][i] and 'Akullikassaap' in settings['validation_files'][i]:
        name = settings['validation_files'][i]
        
#        if '79North' not in name and '79North' not in name and 'Spaltegletsjer' not in name and 'Sermikassak' not in name and 'Upernavik-NW' not in name and 'Kronborg' not in name:
#            if 'Upernavik-NW' in name or '79North' in name or 'Spaltegletsjer' in name or 'Sermikassak' in name:
#        if 'Upernavik' in name:
        domain = name.split(os.path.sep)[-1].split('_')[0]
#        if domain not in domains:
#        if name not in settings['validation_files_val']:
        if True:
            preprocess(i, settings, metrics)
            process(settings, metrics)
            postprocess(settings, metrics)
#            break
    #Print statistics
#    print_calfin_domain_metrics(settings, metrics)
#    print_calfin_all_metrics(settings, metrics)
#    output_calendar_csv(settings, metrics)

    return settings, metrics


def initialize(img_size):
    #initialize settings and model if not already done
    plotting = True
    show_plots = True
    saving = True
    rerun = False

    #Initialize plots
    plt.close('all')
    font = {'family' : 'normal',
            'size'   : 14}
    plt.rc('font', **font)

    validation_files_train = glob.glob(r"../training/data/train/*B[0-9].png")
    validation_files_val = glob.glob(r"../training/data/train/training/data/validation/*B[0-9].png")
    validation_files = validation_files_val + validation_files_train
#    validation_files = validation_files_val
    
    #Initialize output folders
    dest_root_path = r"../outputs/mask_extractor"
    dest_path_qa = os.path.join(dest_root_path, 'quality_assurance')
    dest_path_qa_bad = os.path.join(dest_root_path, 'quality_assurance_bad')
    if not os.path.exists(dest_root_path):
        os.mkdir(dest_root_path)
    if not os.path.exists(dest_path_qa):
        os.mkdir(dest_path_qa)
    if not os.path.exists(dest_path_qa_bad):
        os.mkdir(dest_path_qa_bad)
    for domain in os.listdir(dest_path_qa):
        os.mkdir(os.path.join(dest_path_qa_bad, domain))
            

    scaling = 96.3 / 1.97
    full_size = 256
    stride = 16

    #Intialize processing pipeline variables
    settings = dict()
    settings['driver'] = 'mask_extractor'
    settings['validation_files'] = validation_files
    settings['date_index'] = 3 #The position of the date when the name is split by '_'. Used to differentiate between TerraSAR-X images.
    settings['log_file_name'] = 'logs_mask_extractor.txt'
#    settings['model'] = model
    settings['results'] = []
    settings['plotting'] = plotting
    settings['show_plots'] = show_plots
    settings['saving'] = saving
    settings['rerun'] = rerun
    settings['full_size'] = full_size
    settings['img_size'] = img_size
    settings['stride'] = stride
    settings['line_thickness'] = 3
    settings['kernel'] = cv2.getStructuringElement(cv2.MORPH_RECT, (settings['line_thickness'], settings['line_thickness']))
    settings['confidence_kernel'] = cv2.getStructuringElement(cv2.MORPH_RECT, (settings['line_thickness']*5, settings['line_thickness']*5))
    settings['fjord_boundaries_path'] = r"../training/data/fjord_boundaries"
    settings['tif_source_path'] = r"../preprocessing/calvingfrontmachine/CalvingFronts/tif"
    settings['dest_path_qa'] = dest_path_qa
    settings['dest_root_path'] = dest_root_path
    settings['save_path'] = r"../processing/landsat_preds"
    settings['dest_path_qa_bad'] = dest_path_qa_bad
    settings['save_to_all'] = False
    settings['total'] = len(validation_files)
    settings['empty_image'] = np.zeros((settings['full_size'], settings['full_size']))
    settings['scaling'] = scaling
    settings['domain_scalings'] = dict()
    settings['mask_confidence_strength_threshold'] = 0.5
    settings['edge_confidence_strength_threshold'] = 0.5
    settings['sub_padding_ratio'] = 1.5
    settings['edge_detection_threshold'] = 0.25 #Minimum confidence threshold for a prediction to be contribute to edge size
    settings['edge_detection_size_threshold'] = full_size / 8 #32 minimum pixel length required for an edge to trigger a detection
    settings['mask_detection_threshold'] = 0.5 #Minimum confidence threshold for a prediction to be contribute to edge size
    settings['mask_detection_ratio_threshold'] = 32 #if land/ice area is 32 times bigger than ocean/mélange, classify as no front/unconfident prediction
    settings['mask_edge_buffered_mean_threshold'] = 0.13 #threshold deviation of the mean of mask pixels around the deteccted edge from 0 (mask-edge agreement = 0.0 deviation
    settings['image_settings'] = dict()
    settings['negative_image_names'] = []

    metrics = dict()
    metrics['confidence_skip_count'] = 0
    metrics['no_detection_skip_count'] = 0
    metrics['front_count'] = 0
    metrics['image_skip_count'] = 0
    metrics['mean_deviations_pixels'] = np.array([])
    metrics['mean_deviations_meters'] = np.array([])
    metrics['validation_distances_pixels'] = np.array([])
    metrics['validation_distances_meters'] = np.array([])
    metrics['domain_mean_deviations_pixels'] = defaultdict(lambda: np.array([]))
    metrics['domain_mean_deviations_meters'] = defaultdict(lambda: np.array([]))
    metrics['domain_validation_distances_pixels'] = defaultdict(lambda: np.array([]))
    metrics['domain_validation_distances_meters'] = defaultdict(lambda: np.array([]))
    metrics['domain_validation_edge_ious'] = defaultdict(lambda: np.array([]))
    metrics['domain_validation_mask_ious'] = defaultdict(lambda: np.array([]))
    metrics['domain_validation_calendar'] = defaultdict(lambda: dict((k, 0) for k in range(1972, datetime.datetime.now().year)))
    metrics['resolution_deviation_array'] = np.zeros((0,2))
    metrics['validation_edge_ious'] = np.array([])
    metrics['validation_mask_ious'] = np.array([])
    metrics['resolution_iou_array'] = np.zeros((0,2))
    metrics['true_negatives'] = 0
    metrics['false_negatives'] = 0
    metrics['false_positive'] = 0
    metrics['true_positives'] = 0

    #Each 256x256 image will be split into 9 overlapping 224x224 patches to reduce boundary effects
    #and ensure confident predictions. To normalize this when overlaying patches back together,
    #generate normalization image that scales the predicted image based on number of patches each pixel is in.
    strides = int((full_size - img_size) / stride + 1) #(256-224 / 16 + 1) = 3
    pred_norm_image = np.zeros((full_size, full_size, 3))
    pred_norm_patch = np.ones((img_size, img_size, 2))
    for x in range(strides):
        for y in range(strides):
            x_start = x * stride
            x_end = x_start + img_size
            y_start = y * stride
            y_end = y_start + img_size
            pred_norm_image[x_start:x_end, y_start:y_end, 0:2] += pred_norm_patch
    settings['pred_norm_image'] = pred_norm_image
    
    return settings, metrics


if __name__ == '__main__':
    #Initialize model once, and setup variable passing/main function. Must be done in global namespace to benefit from model reuse.
    img_size = 224
#    try:
#        model
#    except NameError:
#        model = compile_model(img_size)
    settings, metrics = initialize(img_size)

    #Execute calving front extraction pipeline.
#    main(settings, metrics)


