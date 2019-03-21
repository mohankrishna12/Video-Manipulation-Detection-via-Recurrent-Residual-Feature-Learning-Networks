import os
import numpy as np 
import config
from keras.preprocessing.image import img_to_array, load_img
import cv2
import glob
import csv
from tqdm import tqdm
from keras.utils import to_categorical, Sequence
import h5py

class DataSet():

    def __init__(self):
        self.min_seq_length = config.MIN_SEQ_LENGTH
        self.max_seq_length = config.MAX_SEQ_LENGTH

        self.sequence_path = os.path.join('data', 'sequences')
        self.csv_data = self.get_csv_data()
        self.classes = self.get_classes()
        self.csv_data = self.clean_data()
        
    def get_csv_data(self):
        with open(os.path.join('data', 'data_file.csv'), 'r') as fin:
            reader = csv.reader(fin)
            data = list(reader)
        return data 

    def get_classes(self):
        classes = []
        for item in self.csv_data:
            if item[1] not in classes:
                classes.append(item[1])
        
        classes = sorted(classes)
        return classes
    
    def clean_data(self):
        cleaned = []
        for item in self.csv_data:
            if int(item[3])>= self.min_seq_length and int(item[3])<= self.max_seq_length:
                cleaned.append(item)
        return cleaned

    def one_hot(self, class_str):
        label_encoded = self.classes.index(class_str)
        label_hot = to_categorical(label_encoded, len(self.classes))
        return label_hot

    def split_train_test(self):
        train = []
        test = []
        for item in self.csv_data:
            if item[0] == 'train':
                train.append(item)
            else:
                test.append(item)
        return train, test
    
    def get_frames_for_sample(self, csv_row):
        path = os.path.join(self.sequence_path, csv_row[0], csv_row[1])
        filename = csv_row[2]
        images = sorted(glob.glob(os.path.join(path, filename+'*.jpg')))
        return images

    def all_data(self, trainTest):
        train, test = self.split_train_test()
        csv_data = train if trainTest == 'train' else test

        x, y = [], []
        for row in csv_data:
            frames = self.get_frames_for_sample(row)
            # sequence = self.build_image_sequence(frames)[:self.min_seq_length]
            sequence = self.build_image_sequence(frames)
            
            vidClass = row[1]
            if vidClass == 'class2':
                aug_len = 10
                start = np.random.randint(len(sequence)-aug_len)
                for i in range(start, start+aug_len):
                    sequence[i]=np.zeros(sequence[i].shape)
            
            x.append(np.array(sequence))
            y.append(self.one_hot(row[1]))
        
        return np.array(x), np.array(y)





    def process_image(self, image_path):
        """
        Load image from a path into array, and normalize to 0-1. 
        """
        image = load_img(image_path, target_size=(config.IMG_HEIGHT, config.IMG_WIDTH))
        img_arr = img_to_array(image)
        x = (img_arr / 255.).astype(np.float32)
        return x


    def build_image_sequence(self, frames):
        return [self.process_image(x) for x in frames]


    def dumpNumpyFiles(self, trainTest):

        outPath = os.path.join(self.sequence_path, 'npz', trainTest)
        os.makedirs(outPath, exist_ok=True)

        train, test = self.split_train_test()
        csv_data = train if trainTest == 'train' else test

        x, y = [], []
        for k in tqdm(range(len(csv_data))):
            row = csv_data[k]
            frames = self.get_frames_for_sample(row)
            sequence = self.build_image_sequence(frames)[:self.min_seq_length]
            # sequence = self.build_image_sequence(frames)
            
            vidClass = row[1]
            if vidClass == 'class2':
                aug_len = 10
                start = np.random.randint(len(sequence)-aug_len)
                for i in range(start, start+aug_len):
                    sequence[i]=np.zeros(sequence[i].shape)
            

            # x.append(np.array(sequence))
            # y.append(self.one_hot(row[1]))
            vidName = row[2]
            np.savez_compressed(os.path.join(outPath, vidName +'.npz'), x=np.array(sequence), y=self.one_hot(vidClass))
        
        
class DataGenerator(Sequence):
    def __init__(self, trainTest='train', batch_size=1):
        self.trainTest = trainTest
        self.files = glob.glob(os.path.join('data', 'sequences', 'npz', self.trainTest, '*.npz'))
        self.data_length = len(self.files)
        self.batch_size = batch_size
        self.batch_num = 0

        self.on_epoch_end()
    
    def __len__(self):
        return int(np.floor(self.data_length / self.batch_size))

    def __getitem__(self, index):
        x, y = [], []

        batch_files = self.files[self.batch_num*self.batch_size:(self.batch_num+1)*self.batch_size]

        for f in batch_files:
            sequence = np.load(f)
            x.append(sequence['x'])
            y.append(sequence['y'])

        self.batch_num += 1

        return np.array(x), np.array(y)
    
    def on_epoch_end(self):
        np.random.shuffle(self.files)
        self.batch_num = 0
   

class Preprocessing():
    def __init__(self):
        self.video_path = os.path.join('data', 'videos')
        self.sequence_path = os.path.join('data', 'sequences')
        
        os.makedirs(os.path.join(self.sequence_path, 'train'), exist_ok=True)
        os.makedirs(os.path.join(self.sequence_path, 'test'), exist_ok=True)

    
    def extractAllVideos(self):
        data_file = []
        folders = ['train', 'test']
        for folder in folders:
            class_folders = glob.glob(os.path.join(self.video_path, folder, '*'))
            
            for vid_class in class_folders:
                class_files = glob.glob(os.path.join(vid_class, '*.avi'))
                
                for video_path in class_files:
                    trainTest, vidClass, vidName, filename = self.video_parts(video_path)
                    n_frames = self.extractFrames(video_path)
                    data_file.append([trainTest, vidClass, vidName, n_frames])
        
        with open(os.path.join('data', 'data_file.csv'), 'w') as fout:
            writer = csv.writer(fout)
            writer.writerows(data_file)



    def extractFrames(self, video_path):
        trainTest, vidClass, vidName, filename = self.video_parts(video_path)
        # vidName = os.path.basename(os.path.normpath(video_path)).split('.')[0]
        # vidClass = video_path.split(os.sep)[-2]
        # trainTest = video_path.split(os.sep)[-3]
        outPath = os.path.join(self.sequence_path, trainTest, vidClass)
        
        if not os.path.isdir(outPath): os.makedirs(outPath)

        vidcap = cv2.VideoCapture(video_path)
        success,image = vidcap.read()
        count = 1
        while success:
            cv2.imwrite(os.path.join(outPath,  vidName + "-%04d.jpg" % count), image)     # save frame as JPEG file      
            success,image = vidcap.read()
            # print('Read a new frame: ', success)
            count += 1
        count-=1
        return count

    def video_parts(self, video_path):
         parts = video_path.split(os.path.sep)
         filename = parts[-1]
         vidName = filename.split('.')[0]
         vidClass = parts[-2]
         trainTest = parts[-3]
         return trainTest, vidClass, vidName, filename