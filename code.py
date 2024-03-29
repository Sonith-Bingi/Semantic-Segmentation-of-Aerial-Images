# -*- coding: utf-8 -*-


!pip install segmentation-models-pytorch
!pip install -U git+https://github.com/albumentations-team/albumentations
!pip install --upgrade opencv-contrib-python


import sys
sys.path.append('/content/Road_seg_dataset')

import torch
import cv2

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from tqdm import tqdm

import helper

"""#**Configurations**"""

CSV_FILE = '/content/Road_seg_dataset/train.csv'
DATA_DIR = '/content/Road_seg_dataset/'
DEVICE = 'cuda'
EPOCHS = 25
LR = 0.003
BATCH_SIZE = 5
IMG_SIZE = 512
ENCODER = 'timm-efficientnet-b0'
WEIGHTS = 'imagenet'

df =pd.read_csv(CSV_FILE)
df.head()

idx = 2
row = df.iloc [idx]
image_path = DATA_DIR + row.images
mask_path = DATA_DIR + row. masks
image = cv2.imread(image_path)
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
mask = cv2.imread (mask_path, cv2.IMREAD_GRAYSCALE) / 255

f, (ax1, ax2) = plt.subplots(1, 2, figsize=(10,5))

ax1.set_title('IMAGE')
ax1.imshow(image)

ax2.set_title('GROUND TRUTH')
ax2.imshow(mask,cmap = 'gray')

train_df, valid_df = train_test_split(df, test_size=0.20, random_state=42)
len(train_df)

"""#**Augmentation Functions**"""

import albumentations as A

def get_train_augs():
  return A.Compose([
      A.Resize( IMG_SIZE, IMG_SIZE),
      A.HorizontalFlip (p = 0.5),
      A.VerticalFlip (p = 0.5)])
def get_valid_augs():
  return A.Compose([
      A.Resize(IMG_SIZE, IMG_SIZE)
])

"""#**Creation of Custom Dataset**"""

from torch.utils.data import Dataset

class SegmentationDataset(Dataset):

    def __init__(self, df, augmentations):
        self.df = df
        self.augmentations = augmentations

    def __len__(self):
        return len(self.df)
    def __getitem__(self, idx):
        row= df.iloc [idx]
        image_path = DATA_DIR+ row.images
        mask_path = DATA_DIR+ row.masks

        image = cv2.imread(image_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) #{h, W, c)

        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)#(h, w)
        mask = np.expand_dims(mask, axis = -1) #(h, W, c)

        if self.augmentations:
            data = self.augmentations(image= image, mask= mask)
            image = data['image'] #(h, w, C)
            mask = data['mask']

        image = np.transpose(image, (2, 0, 1)).astype(np.float32) #(c, h, w)
        mask = np.transpose(mask, (2, 0, 1)).astype(np.float32) #(c, h, w)

        image=torch.Tensor(image) / 255.0
        mask=torch.round(torch.Tensor(mask) / 255.0)

        return image, mask

trainset = SegmentationDataset(train_df, get_train_augs())
validset = SegmentationDataset(valid_df, get_valid_augs())

print(f'Size of trainset: {len(trainset)}')
print(f'Size of validset: {len(validset)}')

idx = 69
image, mask = trainset[idx]
helper.show_image(image, mask)

"""#**Loading dataset into batches**"""

from torch.utils.data import DataLoader

trainloader = DataLoader(trainset, batch_size=BATCH_SIZE, shuffle = True)
validloader = DataLoader(validset, batch_size=BATCH_SIZE)

print(f'Total no. of batched in trainloader : {len(trainloader)}')
print(f'Total no. of batched in validloader : {len(validloader)}')

for images, masks in trainloader:
    print(f"One batch image shape : {images.shape}")
    print(f"One batch mask shape : {masks.shape}")
    break;

"""#**Create Segmentation Model**"""

import segmentation_models_pytorch as smp
from segmentation_models_pytorch.losses import DiceLoss
from torch import nn

import gc

gc.collect()

torch.cuda.empty_cache()

"""##**MODEL 1: UNet with EfficientNetb0 Encoder**"""

class SegmentationModel1 (nn.Module) :
    def __init__(self):
        super(SegmentationModel1,self).__init__()

        self.backbone = smp.Unet(
            encoder_name = 'timm-efficientnet-b0',
            encoder_weights = WEIGHTS,
            in_channels = 3,
            classes = 1,
        )
    def forward (self, images, masks = None):
      logits = self. backbone (images)
      if masks != None:
          return logits, DiceLoss (mode = 'binary')(logits, masks) + nn.BCEWithLogitsLoss()(logits, masks)
      return logits

"""##**MODEL 2: UNet with EfficientNetb3 Encoder**"""

class SegmentationModel2 (nn.Module) :
    def __init__(self):
        super(SegmentationModel2,self).__init__()

        self.backbone = smp.Unet(
            encoder_name = 'timm-efficientnet-b3',
            encoder_weights = WEIGHTS,
            in_channels = 3,
            classes = 1,
        )
    def forward (self, images, masks = None):
      logits = self. backbone (images)
      if masks != None:
          return logits, DiceLoss (mode = 'binary')(logits, masks) + nn.BCEWithLogitsLoss()(logits, masks)
      return logits

"""##**MODEL 3: UNet++ with EfficientNetb0 Encoder**"""

class SegmentationModel3 (nn.Module) :
    def __init__(self):
        super(SegmentationModel3,self).__init__()

        self.backbone = smp.UnetPlusPlus(
            encoder_name = 'timm-efficientnet-b3',
            encoder_weights = WEIGHTS,
            in_channels = 3,
            classes = 1,
        )
    def forward (self, images, masks = None):
      logits = self. backbone (images)
      if masks != None:
          return logits, DiceLoss (mode = 'binary')(logits, masks) + nn.BCEWithLogitsLoss()(logits, masks)
      return logits

model1 = SegmentationModel1()
model1.to(DEVICE);

model2 = SegmentationModel2()
model2.to(DEVICE);

model3 = SegmentationModel3()
model3.to(DEVICE);

"""#**Training and Validation Functions**"""

def train_fn(dataloader, model, optimizer) :
    model.train() # Turn ON d ropout, batchnorm, etc..
    total_loss = 0.0
    for images, masks in tqdm (dataloader):
        images = images.to (DEVICE)
        masks = masks.to (DEVICE)
        optimizer.zero_grad ()
        logits, loss = model (images, masks)
        loss.backward ()
        optimizer. step()
        total_loss += loss.item()
    return total_loss / len (dataloader)

def eval_fn(dataloader, model):
    model.eval() # Turn OFF dropout, batchno rm, etc.
    total_loss = 0.0
    with torch.no_grad():
        for images, masks in tqdm (dataloader):
            images = images.to(DEVICE)
            masks = masks.to(DEVICE)
            logits, loss = model(images, masks)
            total_loss += loss.item()
        return total_loss / len(dataloader)

"""#**Training the Model**"""

optimizer1 = torch.optim.Adam(model1.parameters(), lr= LR)
optimizer2 = torch.optim.Adam(model2.parameters(), lr= LR)
optimizer3 = torch.optim.Adam(model3.parameters(), lr= LR)

EPOCHS=30
best_loss1 = np.Inf
best_loss2 = np.Inf
best_loss3 = np.Inf

for i in range(EPOCHS):
    train_loss1 = train_fn(trainloader, model1, optimizer1)
    valid_loss1 = eval_fn(validloader, model1)
    if valid_loss1 < best_loss1:
        torch.save(model1.state_dict(), "best-model1.pt")
        print("SAVED-MODEL")
        best_loss1 = valid_loss1
    print(f"Epoch : {i+1} Train Loss : {train_loss1} Valid Loss : {valid_loss1}")

    train_loss2 = train_fn(trainloader, model2, optimizer2)
    valid_loss2 = eval_fn(validloader, model2)
    if valid_loss2 < best_loss2:
        torch.save(model2.state_dict(), "best-model2.pt")
        print("SAVED-MODEL")
        best_loss2 = valid_loss2
    print(f"Epoch : {i+1} Train Loss : {train_loss2} Valid Loss : {valid_loss2}")

    train_loss3 = train_fn(trainloader, model3, optimizer3)
    valid_loss3 = eval_fn(validloader, model3)
    if valid_loss3 < best_loss3:
        torch.save(model3.state_dict(), "best-model3.pt")
        print("SAVED-MODEL")
        best_loss3 = valid_loss3
    print(f"Epoch : {i+1} Train Loss : {train_loss3} Valid Loss : {valid_loss3}")

"""#**Outputs**"""

def displaymodel1(idx):
  model1.load_state_dict(torch.load('/content/best-model1.pt'))
  image, mask = validset[idx]
  logits_mask1 = model1(image.to(DEVICE).unsqueeze(0)) #(c, h, w) -> (b, c, h, w)
  global pred_mask1
  pred_mask1 = torch.sigmoid(logits_mask1)
  pred_mask1 = (pred_mask1 > 0.5)*1.0
  print('MODEL 1 OUTPUT')
  helper.show_image(image, mask, pred_mask1.detach().cpu().squeeze(0))

idx= 9
displaymodel1(idx)

def displaymodel2(idx):
  model2.load_state_dict(torch.load('/content/best-model2.pt'))
  image, mask = validset[idx]
  logits_mask2 = model2(image.to(DEVICE).unsqueeze(0)) #(c, h, w) -> (b, c, h, w)
  global pred_mask2
  pred_mask2 = torch.sigmoid(logits_mask2)
  pred_mask2 = (pred_mask2 > 0.5)*1.0
  print('MODEL 2 OUTPUT')
  helper.show_image(image, mask, pred_mask2.detach().cpu().squeeze(0))

idx= 9
displaymodel2(idx)

def displaymodel3(idx):
  model3.load_state_dict(torch.load('/content/best-model3.pt'))
  image, mask3 = validset[idx]
  logits_mask3 = model3(image.to(DEVICE).unsqueeze(0)) #(c, h, w) -> (b, c, h, w)
  global pred_mask3
  pred_mask3 = torch.sigmoid(logits_mask3)
  pred_mask3 = (pred_mask3 > 0.5)*1.0
  print('MODEL 3 OUTPUT')
  helper.show_image(image, mask, pred_mask3.detach().cpu().squeeze(0))

idx= 9
displaymodel3(idx)

idx=69

def displayAllModels():
  fig = plt.figure(figsize=(10,10))
  ax1 = fig.add_subplot(2,2,1)
  ax1.imshow(pred_mask1.detach().cpu().squeeze(0).squeeze(),cmap='gray')
  ax2 = fig.add_subplot(2,2,2)
  ax2.imshow(pred_mask2.detach().cpu().squeeze(0).squeeze(),cmap='gray')
  ax3 = fig.add_subplot(2,2,3)
  ax3.imshow(pred_mask3.detach().cpu().squeeze(0).squeeze(),cmap='gray')

displayAllModels()

"""#**JACCARD SCORE**"""

from sklearn.metrics import jaccard_score
def calc_jaccard(model,i):

  image, mask = validset[i]
  logits_mask = model(image.to(DEVICE).unsqueeze(0)) #(c, h, w) -> (b, c, h, w)
  pred_mask = torch.sigmoid(logits_mask)
  pred_mask = (pred_mask > 0.5)*1.0
  mask=np.squeeze(np.array(mask))
  pred=np.squeeze(np.array(pred_mask.detach().cpu().squeeze(0)))

  y_true = mask
  y_pred = pred

  labels = [0, 1]
  jaccards = []
  for label in labels:
    jaccard = jaccard_score(y_pred.flatten(),y_true.flatten(), pos_label=label)
    jaccards.append(jaccard)
  return(np.mean(jaccards))


sum1=0
sum2=0
sum3=0
bestj=0

for i in range(len(validset)):
  j1=calc_jaccard(model1,i)
  j2=calc_jaccard(model2,i)
  j3=calc_jaccard(model3,i)
  maxj=max(j1,j2,j3)
  sum1=sum1+j1
  sum2=sum2+j2
  sum3=sum3+j3
  bestj=bestj+maxj



print('MEAN JACCARD SCORE OF MODEL1 = ', sum1/len(validset))
print('MEAN JACCARD SCORE OF MODEL2 = ', sum2/len(validset))
print('MEAN JACCARD SCORE OF MODEL3 = ', sum3/len(validset))
print('JACCARD SCORE OF THE COMBINED MODEL = ', bestj/len(validset))

"""#**COMBINED MODEL**"""

#PROPOSED MODEL
def combinedmodel(idx):
  j1=calc_jaccard(model1,idx)
  j2=calc_jaccard(model2,idx)
  j3=calc_jaccard(model3,idx)
  max=pd.Series([j1,j2,j3]).idxmax()
  #TO KNOW WHICH ONE IS PERFORMING BETTER
  #print(j1,j2,j3)
  #print(MODEL)

  image, mask = validset[idx]

  if (max==0):
    logits_mask1 = model1(image.to(DEVICE).unsqueeze(0))
    pred_mask1 = torch.sigmoid(logits_mask1)
    pred_mask1 = (pred_mask1 > 0.5)*1.0
    helper.show_image(image, mask, pred_mask1.detach().cpu().squeeze(0))

  elif(max==1):
    logits_mask2 = model2(image.to(DEVICE).unsqueeze(0))
    pred_mask2 = torch.sigmoid(logits_mask2)
    pred_mask2 = (pred_mask1 > 0.5)*1.0
    helper.show_image(image, mask, pred_mask2.detach().cpu().squeeze(0))

  else:
    logits_mask3 = model3(image.to(DEVICE).unsqueeze(0))
    pred_mask3 = torch.sigmoid(logits_mask3)
    pred_mask3 = (pred_mask3 > 0.5)*1.0
    helper.show_image(image, mask, pred_mask3.detach().cpu().squeeze(0))

combinedmodel(21)
combinedmodel(34)
combinedmodel(44)
combinedmodel(22)
