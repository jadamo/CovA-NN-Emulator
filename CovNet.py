import torch
import torch.nn as nn
from torch.nn import functional as F
from os.path import exists
import numpy as np

# For now, let's try just using simple fully-connected network
class Network_Full(nn.Module):

    def __init__(self, D_in, D_out):

        super().__init__()
        self.h1 = nn.Linear(D_in, 64)  # Hidden layer
        self.h2 = nn.Linear(64, 128)
        self.h3 = nn.Linear(128, 256)
        self.h4 = nn.Linear(256, 512)  # Hidden layer
        self.h5 = nn.Linear(512, 1024)  # Hidden layer
        self.h6 = nn.Linear(1024, 5000)  # Hidden layer
        self.h7 = nn.Linear(5000, D_out)
        self.out = nn.Linear(D_out, D_out)  # Output layer

    # Define the forward propagation of the model
    def forward(self, X):
        # Note here we use the funtional version of ReLU defined in the
        # nn.functional module.
        w = F.leaky_relu(self.h1(X))
        w = F.leaky_relu(self.h2(w))
        w = F.leaky_relu(self.h3(w))
        w = F.leaky_relu(self.h4(w))
        w = F.leaky_relu(self.h5(w))
        w = F.leaky_relu(self.h6(w))
        w = F.leaky_relu(self.h7(w))
        return self.out(w)

#network to go from parameters to features
class Network_Features(nn.Module):
    def __init__(self, num_params, num_features):
        super().__init__()
        self.h1 = nn.Linear(num_params, 10)  # Hidden layer
        self.h2 = nn.Linear(10, 25)
        self.h3 = nn.Linear(25, 50)
        self.h4 = nn.Linear(50, 75)  # Hidden layer
        self.h5 = nn.Linear(75, num_features)
        self.out = nn.Linear(num_features, num_features)  # Output layer

    # Define the forward propagation of the model
    def forward(self, X):
        # Note here we use the funtional version of ReLU defined in the
        # nn.functional module.
        w = F.leaky_relu(self.h1(X))
        w = F.leaky_relu(self.h2(w))
        w = F.leaky_relu(self.h3(w))
        w = F.leaky_relu(self.h4(w))
        w = F.leaky_relu(self.h5(w))
        return self.out(w)

class Block_Encoder(nn.Module):
    """
    Encoder block for a Variational Autoencoder (VAE). Input is an analytical covariance matrix, 
    and the output is the normal distribution of a latent feature space
    """
    def __init__(self):
        super().__init__()
        # TODO: find out if using channels and batch normalization would be good to include
        self.C1 = nn.Conv2d(1, 2, 4, stride=2, padding=1) # 50x50
        self.C2 = nn.Conv2d(2, 2, 3, padding=1) # 50x50
        self.C3 = nn.Conv2d(2, 4, 4, stride=2, padding=1) # 25x25
        self.C4 = nn.Conv2d(4, 4, 3) # 23x23
        self.C5 = nn.Conv2d(4, 6, 3, stride=2, padding=1) # 12x12
        self.C6 = nn.Conv2d(6, 6, 3) # 10x10

        self.f1 = nn.Linear(600, 400)
        self.f2 = nn.Linear(400, 200)
        # 2 seperate layers - one for mu and one for log_var
        self.fmu = nn.Linear(200, 100)
        self.fvar = nn.Linear(200, 100)

    def reparameterize(self, mu, log_var):
        if self.training:
            std = torch.exp(0.5*log_var)
            #eps = torch.randn_like(std)
            eps = std.data.new(std.size()).normal_()
            return mu + (eps * std) # sampling as if coming from the input space
        else:
            return mu

    def forward(self, X):
        X = F.leaky_relu(self.C1(X))
        X = F.leaky_relu(self.C2(X))
        X = F.leaky_relu(self.C3(X))
        X = F.leaky_relu(self.C4(X))
        X = F.leaky_relu(self.C5(X))
        X = F.leaky_relu(self.C6(X))

        X = X.view(-1, 1, 600)
        X = F.leaky_relu(self.f1(X))
        X = F.leaky_relu(self.f2(X))
        mu = F.leaky_relu(self.fmu(X))
        log_var = torch.sigmoid(self.fvar(X))

        z = self.reparameterize(mu, log_var)
        return z, mu, log_var

class Block_Decoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.f1 = nn.Linear(100, 200)  # Hidden layer
        self.f2 = nn.Linear(200, 400)
        self.f3 = nn.Linear(400, 600)

        self.C1 = nn.ConvTranspose2d(6, 6, 3) #12x12
        self.C2 = nn.ConvTranspose2d(6, 4, 3, stride=2, padding=1) #23x23
        self.C3 = nn.ConvTranspose2d(4, 4, 3) #25x25
        self.C4 = nn.ConvTranspose2d(4, 2, 3, stride=2, padding=1) #47x47
        #self.C5 = nn.ConvTranspose2d(1, 1, 3) #49x49
        self.out = nn.ConvTranspose2d(2, 1, 6, stride=2, padding=1) #100x100

    def forward(self, X):
        X = F.leaky_relu(self.f1(X))
        X = F.leaky_relu(self.f2(X))
        X = F.leaky_relu(self.f3(X))

        X = X.view(-1, 6, 10, 10)
        X = F.leaky_relu(self.C1(X))
        X = F.leaky_relu(self.C2(X))
        X = F.leaky_relu(self.C3(X))
        X = F.leaky_relu(self.C4(X))
        #X = F.leaky_relu(self.C5(X))
        X = F.leaky_relu(self.out(X))
        X = X.view(-1, 100, 100)
        return X

class Network_VAE(nn.Module):
    def __init__(self):
        super().__init__()
        self.Encoder = Block_Encoder()
        self.Decoder = Block_Decoder()

    def forward(self, X):
        # run through the encoder
        z, mu, log_var = self.Encoder(X)#.view(-1, 2, 50)
        assert not True in torch.isnan(z)
        #print("After encoder:",  torch.min(z), torch.max(z))
        # The encoder outputs a distribution, so we need to draw some random sample from that
        # distribution in order to go through the decoder
        # mu = X[:, 0, :] # the first feature values as mean
        # log_var = X[:, 1, :] # the other feature values as variance
        # z = self.reparameterize(mu, log_var)

        # run through the decoder
        X = self.Decoder(z)
        assert not True in torch.isnan(X)
        return X, mu, log_var

# Dataset class to handle making training / validation / test sets
class MatrixDataset(torch.utils.data.Dataset):
    def __init__(self, data_dir, N, offset, train_log, train_inverse):
        self.params = torch.zeros([N, 6])
        self.matrices = torch.zeros([N, 100, 100])
        self.features = torch.zeros(N, 100)
        self.offset = offset
        self.N = N

        self.has_features = False

        for i in range(N):

            idx = i + offset
            # skip this file if it doesn't exist (handles incomplete training sets)
            #if exists(data_dir+"CovA-"+f'{idx:04d}'+".txt") == False:
            #    continue

            file = data_dir+"CovA-"+f'{idx:05d}'+".txt"

            # TODO: Convert this to pytorch so it can directly load to GPU
            # load in parameters
            f = open(file)
            header = f.readline()
            header = f.readline()
            f.close()
            header = torch.from_numpy(np.fromstring(header[2:-1], sep=","))
            self.params[i] = torch.cat([header[0:4], header[5:]])
            # load in matrix
            self.matrices[i] = torch.from_numpy(np.loadtxt(file, skiprows=2))

            if train_log == True:
                self.matrices[i] = symmetric_log(self.matrices[i])

    def add_features(self, z):
        self.features = z

    def __len__(self):
        return self.N

    def __getitem__(self, idx):
        if self.has_features:
            return self.params[idx], self.matrices[idx], self.features[idx]
        else:
            return self.params[idx], self.matrices[idx]

def VAE_loss(prediction, target, mu, log_var):
    """
    Calculates the KL Divergence and reconstruction terms and returns the full loss function
    """
    #BCE = F.binary_cross_entropy(prediction, target, reduction="sum")
    RLoss = F.l1_loss(prediction, target, reduction="sum")
    KLD = 0.5 * torch.sum(log_var.exp() - log_var - 1 + mu.pow(2))
    #print(RLoss, KLD)
    #print(mu, log_var, log_var.exp())
    return RLoss + KLD

def matrix_loss(prediction, target, norm):
    """
    Custom loss function that includes a penalizing term for non-symmetric outputs
    """
    # normal l-n norm term
    l1 = torch.pow(prediction - target, norm)
    l1 = torch.mean(l1)

    # term that's non-zero for non-symmetric matrices
    asymmetric_predict = prediction - torch.transpose(prediction,1,2)
    l2 = torch.pow(asymmetric_predict, norm)
    l2 = torch.mean(l2)

    return l1 + l2


def symmetric_log(m):
    """
    Takes a a matrix and returns a piece-wise logarithm for post-processing
    NOTE: entries between 0 and 1 are treated as equal to 1
    sym_log(x) =  log10(x),  x > 1
    sym_log(x) = -log10(-x), x < 0
    """
    pos_m, neg_m = np.ones(m.shape), np.zeros(m.shape)
    pos_idx = np.where(m >= 1)
    neg_idx = np.where(m < 0)
    pos_m[pos_idx] = m[pos_idx]
    neg_m[neg_idx] = m[neg_idx]

    pos_m = np.log10(pos_m)
    # for negative numbers, treat log(x) = -log(-x)
    neg_m[neg_idx] = -np.log10(-1*neg_m[neg_idx])
    return torch.from_numpy(pos_m + neg_m)

def symmetric_exp(m):
    """
    Takes a matrix and returns the piece-wise exponent
    NOTE: this assumes there are no entries with true values between 0 and 1
    sym_exp(x) = 10^x,   x > 0
    sym_exp(x) = -10^-x, x < 0
    This is the reverse operation of symmetric_log
    """
    pos_m, neg_m = np.zeros(m.shape), np.zeros(m.shape)
    pos_idx = np.where(m >= 0)
    neg_idx = np.where(m < 0)
    pos_m[pos_idx] = m[pos_idx]
    neg_m[neg_idx] = m[neg_idx]

    pos_m = 10**pos_m
    pos_m[(pos_m == 1)] = 0
    # for negative numbers, treat log(x) = -log(-x)
    neg_m[neg_idx] = -10**(-1*neg_m[neg_idx])
    return torch.from_numpy(pos_m + neg_m)