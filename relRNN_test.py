#Package imports
import cv2
import math
import sklearn
import random
import progressbar
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from time import time
from scipy import misc
from scipy import ndimage
from IPython import display
from PIL import Image, ImageOps
from IPython.display import YouTubeVideo    
from scipy.ndimage.filters import convolve

from sklearn.cluster import KMeans
import torch
from torch import FloatTensor, dtype, nn


#Subfiles imports
from RNN.RNN import RNN_classifier
from RNN.RNN import RNN_commeavant
from Shrec2017.ShrecDataset import ShrecDataset
from Relational_RNN.relational_network import RelationalNetwork
from Embedding.Emb_CNN import Emb_CNN

from Relational_RNN.Rel_CNN import Rel_CNN
from Relational_RNN.Rel_RNN import Rel_RNN
from model_CNN import Video_Analysis_Network
import pickle

def _getSampleAndQuery(Indices, Classes, batchSize, K, C):
    Sample = []
    inds_bis = []
    per_classe = {}
    for classe in C:
        per_classe[classe] = 0

    for i in Indices:
        if per_classe[Classes[i, 0]]<K:
            Sample.append(i)
            per_classe[Classes[i, 0]] += 1
        else:
            inds_bis.append(i)

    if len(inds_bis) < batchSize:
        return None, None, None

    for classe in C:
        if per_classe[classe] != K:
            return None, None, None
    
    np.random.shuffle(inds_bis)
    return Sample, inds_bis[:batchSize], inds_bis[batchSize:]


def __main__():
    video = True
    dataset = ShrecDataset(full=True, rescale=None, video=video)
    train_data, train_target, test_data, test_target = dataset.get_data(training_share=0.9, one_hot=False)
    print(dataset.dataSize, dataset.seqSize, dataset.inputSize, dataset.outputSize, dataset.trainSize)
    print(train_data.shape, train_target.shape, test_data.shape, test_target.shape)
    import sys
    sizes = []
    for i in range(len(train_data)):
        first = dataset.open_data(train_data[0])
        
        first = np.pad(first, [(0, 171-len(first)), (0, 0), (0, 0), (0, 0)])
        print(first.shape)
        print("size ", sys.getsizeof(np.float32(first)))
        sizes.append(sys.getsizeof(np.float32(first)))
    print("mean of ", np.mean(sizes))
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
        print("Using cuda")
    else :
        print("Using cpu")

    embedding_size = 512

    #embedder = Emb_CNN((-1, 1) + dataset.inputSize, dim_concat=None, TimeDistributed = True, device=device)
    #relNet = Rel_RNN((1,) + dataset.inputSize, device=device)
    #model = Video_Analysis_Network(embedder, relNet)
    print(f"in {dataset.inputSize}")
    
    embedder = RNN_classifier(dataset.rescale, dataset.seqSize, embedding_size, device=device)
    relNet = RelationalNetwork(embedder, embedding_size, device=device)
    # embedder = RNN_commeavant(dataset.inputSize, dataset.seqSize, embedding_size, device=device)
    #relNet = RelationalNetwork(embedder, embedding_size, device=device)

    lossHistory = []
    outputs = []
    target = []
    test_Score = []

    adresse = './RNN/checkpoints'

    K = 1 #K-shot learning
    C_train = [2, 3, 4]
    C_eval = [5, 6]
    batchSize = 8
    evalSize = 8
    learningRate = 0.0005 
    epochs = 5
    optimizer = torch.optim.Adam(relNet.parameters(), lr=learningRate)

    affichage = 5
    moyennage = 10
    saving = 10

    """
    bar = progressbar.ProgressBar(maxval=epochs)
    bar.start()
    bar.update(0)
    """
    train_indices = np.where(np.isin(train_target, C_train), np.reshape(np.arange(dataset.trainSize), train_target.shape) , False)
    train_indices = np.array(train_indices[train_indices != [False]])
    np.random.shuffle(np.array(train_indices))
    
    eval_indices = np.where(np.isin(train_target, C_eval), np.reshape(np.arange(dataset.trainSize), train_target.shape) , False)
    eval_indices = np.array(eval_indices[eval_indices != [False]])
    np.random.shuffle(np.array(eval_indices))

    HIST = {'tloss': [], 'tacc':[], 'eacc': []}
    for epoch in range(epochs):
        batch_nb = 1
        Sample_ixs, Query_ixs, train_indices_batch = _getSampleAndQuery(train_indices, Classes=train_target, batchSize=batchSize, K=K, C=C_train)
        eval_sampl, eval_query, eval_indexes = _getSampleAndQuery(eval_indices, Classes=train_target, batchSize=evalSize, K=K, C=C_eval)

        while Query_ixs is not None:
            Sample_set = (dataset.open_datas(train_data[Sample_ixs], video=video).to(device), train_target[Sample_ixs])
            Query_set = (dataset.open_datas(train_data[Query_ixs], video=video).to(device), train_target[Query_ixs])
            batch_loss = relNet.trainSQ(sample=Sample_set, query=Query_set, optim=optimizer)
            in_accuracy = relNet.evalSQ(sample=Sample_set, query=Query_set)
            evalSampleSet = (dataset.open_datas(train_data[eval_sampl], video=video).to(device), train_target[eval_sampl])
            evalQuerySet = (dataset.open_datas(train_data[eval_query], video=video).to(device), train_target[eval_query])
            out_accuracy = relNet.evalSQ(sample=evalSampleSet, query=evalQuerySet)
            print(f"epoch {epoch}, batch nb {batch_nb}, trian loss {batch_loss}, in-distrib acc {in_accuracy}, out-distrib acc {out_accuracy}")
            HIST['tloss'].append(batch_loss)
            HIST['tacc'].append(in_accuracy)
            HIST['eacc'].append(out_accuracy)
            batch_nb+=1
            Sample_ixs, Query_ixs, train_indices_batch = _getSampleAndQuery(train_indices_batch, Classes=train_target, batchSize=batchSize, K=K, C=C_train)
            with open(f"{K}_shot_{len(C_train)}_way_{batchSize}b.pickle", "wb+") as f:
                pickle.dump(HIST, f)
        np.random.shuffle(np.array(train_indices))
        np.random.shuffle(np.array(eval_indices))

if __name__ == "__main__":
    __main__()


""" Naive training
            batch = np.random.choice(dataset.trainSize, batchSize)
            ref_im_ix = batch[-1]
            batch = batch[:-1]
            ref_im, ref_label = train_data[ref_im_ix], train_target[ref_im_ix]
            ref_im = ref_im.reshape([1] + list(ref_im.shape))
            ref_embedding = relNet.embedder(ref_im.float())
            
            output = relNet(train_data[batch].float(), ref_embedding.float())
            y = ref_label == train_target[batch]
            loss = relNet.loss(output.float(), y.float())
            relNet.zero_grad()
            loss.backward()
            optimizer.step()
            print(f"epoch {epoch}, reference {ref_label.item()}, loss {loss.item()}")"""
