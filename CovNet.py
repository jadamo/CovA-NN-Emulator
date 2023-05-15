import torch
import torch.nn as nn
from torch.nn import functional as F
import numpy as np
import time

#torch.set_default_dtype(torch.float64)

class CovNet():

    def __init__(self, net_dir, N, structure_flag=0, train_cholesky=True):
        """
        Initializes the covariance emulator in a warpper class by loading in the trained
        neural networks based on the specified options
        @param net_dir {string} location of trained networks
        @param N {int} the matrix dimensionality
        @param structure_flag {int} flag specifying the specific structure the network is (0 = fully connected ResNet, 1 = CNN ResNet)
        @param train_cholesky {bool} wether or not the emulator was trained on the cholesky decomposition
        """

        self.train_cholesky = train_cholesky
        self.N = N

        self.net_VAE = Network_VAE(structure_flag, train_cholesky).to(try_gpu())
        self.decoder = Block_Decoder(structure_flag, train_cholesky).to(try_gpu())
        self.net_latent = Network_Latent().to(try_gpu())
        self.net_VAE.eval()
        self.decoder.eval()

        self.net_VAE.load_state_dict(torch.load(net_dir+'network-VAE.params'))
        self.decoder.load_state_dict(self.net_VAE.Decoder.state_dict())
        self.net_latent.load_state_dict(torch.load(net_dir+'network-latent.params'))

    def get_covariance_matrix(self, params):
        """
        Uses the emulator to return a covariance matrix
        params -> secondary network -> decoder -> post-processing
        @param params {np array} the list of cosmology parameters to emulator a covariance matrix from
        @return C {np array} the emulated covariance matrix of size (N, N) where N was specified during initialization
        """
        params = torch.from_numpy(params).to(torch.float32)
        z = self.net_latent(params).view(1,6)
        matrix = self.decoder(z).view(1,self.N,self.N)

        matrix = symmetric_exp(matrix).view(self.N,self.N)
        if self.train_cholesky == True:
            matrix = torch.matmul(matrix, torch.t(matrix))

        return matrix.detach().numpy().astype(np.float64)

# ---------------------------------------------------------------------------
# Secondary (parameters -> latent space) network
# ---------------------------------------------------------------------------
class Network_Latent(nn.Module):
    def __init__(self, train_nuisance=False):
        super().__init__()
        self.h1 = nn.Linear(6, 6)  # Hidden layer
        self.h2 = nn.Linear(6, 6)
        self.h3 = nn.Linear(6, 6)
        self.h4 = nn.Linear(6, 6)

        self.h5 = nn.Linear(6, 6)
        self.h6 = nn.Linear(6, 6)
        self.h7 = nn.Linear(6, 6)
        self.h8 = nn.Linear(6, 6)

        self.h9 = nn.Linear(6, 6)
        self.h10 = nn.Linear(6, 6)
        self.h11 = nn.Linear(6, 6)
        self.h12 = nn.Linear(6, 6)

        self.h13 = nn.Linear(6, 6)
        self.h14 = nn.Linear(6, 6)
        self.h15 = nn.Linear(6, 6)
        self.h16 = nn.Linear(6, 6)

        self.h17 = nn.Linear(6, 6)
        self.h18 = nn.Linear(6, 6)
        self.out = nn.Linear(6, 6)  # Output layer

        self.bounds = torch.tensor([[50, 100],
                                    [0.01, 0.3],
                                    [0.25, 1.65],
                                    [1, 4],
                                    [-4, 4],
                                    [-4, 4]])

    def normalize(self, params):

        params_norm = (params - self.bounds[:,0]) / (self.bounds[:,1] - self.bounds[:,0])
        return params_norm

    # Define the forward propagation of the model
    def forward(self, X):

        X = self.normalize(X)
        residual = X

        w = F.leaky_relu(self.h1(X))
        w = F.leaky_relu(self.h2(w))
        w = F.leaky_relu(self.h3(w))
        w = self.h4(w) + residual; residual = w
        w = F.leaky_relu(self.h5(w))
        w = F.leaky_relu(self.h6(w))
        w = F.leaky_relu(self.h7(w))
        w = self.h8(w) + residual; residual = w
        w = F.leaky_relu(self.h9(w))
        w = F.leaky_relu(self.h10(w))
        w = F.leaky_relu(self.h11(w))
        w = self.h12(w) + residual; residual = w
        w = F.leaky_relu(self.h13(w))
        w = F.leaky_relu(self.h14(w))
        w = F.leaky_relu(self.h15(w))
        w = self.h16(w) + residual; residual = w
        w = F.leaky_relu(self.h17(w))
        w = F.leaky_relu(self.h18(w))
        return self.out(w)

# ---------------------------------------------------------------------------
# VAE blocks
# ---------------------------------------------------------------------------
class Block_Full_ResNet(nn.Module):
    def __init__(self, dim_in, dim_out):
        super().__init__()

        self.h1 = nn.Linear(dim_in, dim_out)
        self.bn1 = nn.BatchNorm1d(dim_out)
        self.h2 = nn.Linear(dim_out, dim_out)
        self.bn2 = nn.BatchNorm1d(dim_out)
        self.h3 = nn.Linear(dim_out, dim_out)
        self.bn3 = nn.BatchNorm1d(dim_out)
        self.h4 = nn.Linear(dim_out, dim_out)

        self.bn_skip = nn.BatchNorm1d(dim_out)
        self.skip = nn.Linear(dim_in, dim_out)

    def forward(self, X):
        residual = X
        X = F.leaky_relu(self.bn1(self.h1(X)))
        X = F.leaky_relu(self.bn2(self.h2(X)))
        X = F.leaky_relu(self.bn3(self.h3(X)))

        residual = self.bn_skip(self.skip(residual))
        X = F.leaky_relu(self.h3(X) + residual)
        return X

class Block_CNN_ResNet(nn.Module):
    def __init__(self, C_in, C_out, reverse=False):
        super().__init__()
        if reverse==False:
            self.c1 = nn.Conv2d(C_in, C_out, kernel_size=3, padding=1)
            self.bn1 = nn.BatchNorm2d(C_out)
            self.c2 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.c3 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.c4 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.bn2 = nn.BatchNorm2d(C_out)
            self.c5 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.c6 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.c7 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.bn3 = nn.BatchNorm2d(C_out)
            self.c8 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.c9 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.c10 = nn.Conv2d(C_out, C_out, kernel_size=3, padding=1)
            self.bn4 = nn.BatchNorm2d(C_out)

            self.skip = nn.Conv2d(C_in, C_out, kernel_size=1, padding=0)
            self.pool = nn.MaxPool2d(kernel_size=2,stride=2)
        else:
            self.c1 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.bn1 = nn.BatchNorm2d(C_in)
            self.c2 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.c3 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.c4 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.bn2 = nn.BatchNorm2d(C_in)
            self.c5 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.c6 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.c7 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.bn3 = nn.BatchNorm2d(C_in)
            self.c8 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.c9 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.c10 = nn.ConvTranspose2d(C_in, C_in, kernel_size=3, padding=1)
            self.bn4 = nn.BatchNorm2d(C_in)

            self.skip = nn.ConvTranspose2d(C_in, C_in, kernel_size=1, padding=0)
            self.pool = nn.ConvTranspose2d(C_in, C_out, kernel_size=2,stride=2)

    def forward(self, X):
        residual = X

        X = F.leaky_relu(self.bn1(self.c1(X)))
        X = F.leaky_relu(self.c2(X))
        X = F.leaky_relu(self.c3(X))
        X = F.leaky_relu(self.bn2(self.c4(X)))
        X = F.leaky_relu(self.c5(X))
        X = F.leaky_relu(self.c6(X))
        X = F.leaky_relu(self.bn3(self.c7(X)))
        X = F.leaky_relu(self.c8(X))
        X = F.leaky_relu(self.c9(X))
        X = self.bn4(self.c10(X))

        residual = self.skip(residual)
        X = F.leaky_relu(X + residual)
        X = self.pool(X)
        return X


# ---------------------------------------------------------------------------
# VAE network (Encoder + Decoder)
# ---------------------------------------------------------------------------
class Block_Encoder(nn.Module):
    """
    Encoder block for a Variational Autoencoder (VAE). Input is an analytical covariance matrix, 
    and the output is the normal distribution of a latent feature space
    """
    def __init__(self, structure_flag):
        super().__init__()
        self.structure_flag = structure_flag

        if self.structure_flag == 0:
            self.h1 = nn.Linear(51*25, 1000)
            self.resnet1 = Block_Full_ResNet(1000, 500)
            self.resnet2 = Block_Full_ResNet(500, 100)
            self.h2 = nn.Linear(100, 50)
            self.bn1 = nn.BatchNorm1d(50)
            self.h3 = nn.Linear(50, 25)

        elif self.structure_flag == 1:
            self.c1 = nn.Conv2d(1, 5, kernel_size=(4, 3), padding=1)
            self.resnet1 = Block_CNN_ResNet(5, 10) #(5,50,25) -> (5,25,12)
            self.resnet2 = Block_CNN_ResNet(10, 15) #(5,25,12) -> (7,12,6)
            self.resnet3 = Block_CNN_ResNet(15, 20) #(7,12,6)  -> (9,6,3)
            self.resnet4 = Block_CNN_ResNet(20, 30) #(9,6,3)   -> (9,3,1)

            self.f1 = nn.Linear(90, 50)
            self.f2 = nn.Linear(50, 25)

        # 2 seperate layers - one for mu and one for log_var
        self.fmu = nn.Linear(25, 6)
        self.fvar = nn.Linear(25, 6)

    def reparameterize(self, mu, log_var):
        #if self.training:
        std = torch.exp(0.5*log_var)
        eps = std.data.new(std.size()).normal_()
        return mu + (eps * std) # sampling as if coming from the input space
        #else:
        #    return mu

    def forward(self, X):
        X = rearange_to_half(X, 50)

        if self.structure_flag == 0:
            X = X.view(-1, 51*25)

            X = F.leaky_relu(self.h1(X))
            X = self.resnet1(X)
            X = self.resnet2(X)
            X = F.leaky_relu(self.bn1(self.h2(X)))
            X = F.leaky_relu(self.h3(X))

        elif self.structure_flag == 1:
            X = X.view(-1, 1, 51, 25)
            X = F.leaky_relu(self.c1(X))
            X = self.resnet1(X)
            X = self.resnet2(X)
            X = self.resnet3(X)
            X = self.resnet4(X)
            X = torch.flatten(X, 1, 3)

            X = F.leaky_relu(self.f1(X))
            X = F.leaky_relu(self.f2(X))

        mu = self.fmu(X)
        log_var = self.fvar(X)

        # we're taking the exponent of this, so clamp to "reasonable" values to prevent overflow
        log_var = torch.clamp(log_var, min=-15, max=15)

        # The encoder outputs parameters of some distribution, so we need to draw some random sample from
        # that distribution in order to go through the decoder
        z = self.reparameterize(mu, log_var)
        return z, mu, log_var

class Block_Decoder(nn.Module):
 
    def __init__(self, structure_flag, train_cholesky=True):
        super().__init__()
        self.train_cholesky = train_cholesky
        self.structure_flag = structure_flag

        if self.structure_flag == 0:
            self.h1 = nn.Linear(6, 25)
            self.h2 = nn.Linear(25, 50)
            self.h3 = nn.Linear(50, 100)
            self.resnet1 = Block_Full_ResNet(100, 500)
            self.resnet2 = Block_Full_ResNet(500, 1000)
            self.out = nn.Linear(1000, 51*25)

        elif self.structure_flag == 1:
            self.f1 = nn.Linear(6, 25)
            self.f2 = nn.Linear(25, 50)
            self.f3 = nn.Linear(50, 90)

            self.resnet1 = Block_CNN_ResNet(30, 20, True) #(20,3,1) -> (15,6,2)
            self.c1 = nn.ConvTranspose2d(20, 20, kernel_size=(1,2), padding=0, stride=1)
            self.resnet2 = Block_CNN_ResNet(20, 15, True)   #(4, 6, 3) -> (3, 12, 6)
            self.resnet3 = Block_CNN_ResNet(15, 10, True)   #(3, 12, 6) -> (2, 24, 12)
            self.resnet4 = Block_CNN_ResNet(10, 5, True)   #(2, 24, 12) -> (1, 48, 24)
            self.c2 = nn.ConvTranspose2d(5, 5, kernel_size=(4, 2))
            self.out = nn.ConvTranspose2d(5, 1, kernel_size=3, padding=1)

    def forward(self, X):

        if self.structure_flag == 0:
            X = F.leaky_relu(self.h1(X))
            X = F.leaky_relu(self.h2(X))
            X = F.leaky_relu(self.h3(X))
            X = self.resnet1(X)
            X = self.resnet2(X)
            X = torch.tanh(self.out(X))

        elif self.structure_flag == 1:
            X = F.leaky_relu(self.f1(X))
            X = F.leaky_relu(self.f2(X))
            X = F.leaky_relu(self.f3(X))
            X = X.reshape(-1, 30, 3, 1)
            X = self.resnet1(X)
            X = F.leaky_relu(self.c1(X))
            X = self.resnet2(X)
            X = self.resnet3(X)
            X = self.resnet4(X)
            X = F.leaky_relu(self.c2(X))
            X = self.out(X)

        X = X.view(-1, 51, 25)
        X = rearange_to_full(X, 50, self.train_cholesky)
        return X

class Network_VAE(nn.Module):
    def __init__(self, structure_flag, train_cholesky=True):
        super().__init__()
        self.structure_flag = structure_flag
        self.train_cholesky = train_cholesky
        if structure_flag < 0 or structure_flag >= 3:
            print("ERROR! invalid value for structure flag! Currently can be [0, 1, 2]")
        if structure_flag != 2:
            self.Encoder = Block_Encoder(structure_flag)
            self.Decoder = Block_Decoder(structure_flag, train_cholesky)
        else:
            self.h1 = nn.Linear(6, 25)
            self.resnet1 = Block_Full_ResNet(25, 50)
            self.resnet2 = Block_Full_ResNet(50, 100)
            self.resnet3 = Block_Full_ResNet(100, 500)
            self.resnet4 = Block_Full_ResNet(500, 1000)
            self.out = nn.Linear(1000, 51*25)

            self.bounds = torch.tensor([[50, 100],
                                    [0.01, 0.3],
                                    [0.25, 1.65],
                                    [1, 4],
                                    [-4, 4],
                                    [-4, 4]]).to(try_gpu())

    def normalize(self, params):

        params_norm = (params - self.bounds[:,0]) / (self.bounds[:,1] - self.bounds[:,0])
        return params_norm

    def forward(self, X):
        if self.structure_flag != 2:
            # run through the encoder
            # assumes that z has been reparamaterized in the forward pass
            z, mu, log_var = self.Encoder(X)
            assert not True in torch.isnan(z)

            # run through the decoder
            X = self.Decoder(z)
            X = torch.clamp(X, min=-12, max=12)
            assert not True in torch.isnan(X) 
            assert not True in torch.isinf(X)

            return X, mu, log_var
        else:
            X = self.normalize(X)
            X = F.leaky_relu(self.h1(X))
            X = self.resnet1(X)
            X = self.resnet2(X)
            X = self.resnet3(X)
            X = self.resnet4(X)
            X = torch.tanh(self.out(X))

            X = X.view(-1, 51, 25)
            X = rearange_to_full(X, 50, self.train_cholesky)
            return X


# ---------------------------------------------------------------------------
# Dataset class to handle loading and pre-processing data
# ---------------------------------------------------------------------------
class MatrixDataset(torch.utils.data.Dataset):
    def __init__(self, data_dir, N, offset, 
                 train_nuisance=False, train_cholesky=True, train_gaussian_only=False):
        """
        Initialize and load in dataset for training
        @param data_dir {string} location of training set
        @param N {int} size of training set
        @param offset {int} index number to begin reading training set (used when splitting set into training / validation / test sets)
        @param train_nuisance {bool} whether you will be varying nuisance parameters when training
        @param train_cholesky {bool} whether to represent each matrix as its cholesky decomposition
        @param train_gaussian {bool} whether to store only the gaussian term of the covariance matrix (for testing)
        """

        num_params=6 if train_nuisance==False else 10
        self.params = torch.zeros([N, num_params])
        self.matrices = torch.zeros([N, 50, 50])
        self.features = None
        self.offset = offset
        self.N = N

        self.has_latent_space = False

        self.cholesky = train_cholesky
        self.gaussian_only = train_gaussian_only

        for i in range(N):

            idx = i + offset
            data = np.load(data_dir+"CovA-"+f'{idx:05d}'+".npz")
            self.params[i] = torch.from_numpy(data["params"][:6])

            # store specific terms of each matrix depending on the circumstances
            if self.gaussian_only:
                self.matrices[i] = torch.from_numpy(data["C_G"])
            else:
                self.matrices[i] = torch.from_numpy(data["C_G"] + data["C_SSC"] + data["C_T0"])

        self.params = self.params.to(try_gpu())
        self.matrices = self.matrices.to(try_gpu())

        if train_cholesky:
            self.matrices = torch.linalg.cholesky(self.matrices)

        self.matrices = symmetric_log(self.matrices)

    def add_latent_space(self, z):
        # training latent net seems to be faster on cpu, so move data there
        self.latent_space = z.detach().to(torch.device("cpu"))
        self.params = self.params.to(torch.device("cpu"))
        self.has_latent_space = True

    def __len__(self):
        return self.N

    def __getitem__(self, idx):
        if self.has_latent_space:
            return self.params[idx], self.matrices[idx], self.latent_space[idx]
        else:
            return self.params[idx], self.matrices[idx]
        
    def get_full_matrix(self, idx):
        """
        reverses all data pre-processing to return the full covariance matrix
        """
        # reverse logarithm (always true)
        mat = symmetric_exp(self.matrices[idx])

        if self.cholesky == True:
            mat = torch.matmul(mat, torch.t(mat))

        return mat.detach().numpy()


# ---------------------------------------------------------------------------
# Other helper functions
# ---------------------------------------------------------------------------
def VAE_loss(prediction, target, mu, log_var, beta=1.0):
    """
    Calculates the KL Divergence and reconstruction terms and returns the full loss function
    """
    prediction = rearange_to_half(prediction, 50)
    target = rearange_to_half(target, 50)

    RLoss = F.l1_loss(prediction, target, reduction="sum")
    #RLoss = torch.sqrt(((prediction - target)**2).sum())
    #RLoss = F.mse_loss(prediction, target, reduction="sum")
    KLD = 0.5 * torch.sum(log_var.exp() - log_var - 1 + mu.pow(2))
    #print(RLoss, KLD, torch.amin(prediction), torch.amax(prediction))
    return RLoss + (beta*KLD)

def features_loss(prediction, target):
    """
    Loss function for the parameters -> features network (currently MSE loss)
    """
    loss = F.l1_loss(prediction, target, reduction="sum")
    #loss = F.mse_loss(prediction, target, reduction="sum")

    return loss

def rearange_to_half(C, N):
    """
    Takes a batch of matrices (B, N, N) and rearanges the lower half of each matrix
    to a rectangular (B, N+1, N/2) shape.
    """
    N_half = int(N/2)
    B = C.shape[0]
    L1 = torch.tril(C)[:,:,:N_half]; L2 = torch.tril(C)[:,:,N_half:]
    L1 = torch.cat((torch.zeros((B,1, N_half), device=try_gpu()), L1), 1)
    L2 = torch.cat((torch.flip(L2, [1,2]), torch.zeros((B,1, N_half), device=try_gpu())),1)

    return L1 + L2

def rearange_to_full(C_half, N, train_cholesky=False):
    """
    Takes a batch of half matrices (B, N+1, N/2) and reverses the rearangment to return full,
    symmetric matrices (B, N, N). This is the reverse operation of rearange_to_half()
    """
    N_half = int(N/2)
    B = C_half.shape[0]
    C_full = torch.zeros((B, N,N), device=try_gpu())
    C_full[:,:,:N_half] = C_full[:,:,:N_half] + C_half[:,1:,:]
    C_full[:,:,N_half:] = C_full[:,:,N_half:] + torch.flip(C_half[:,:-1,:], [1,2])
    L = torch.tril(C_full)
    U = torch.transpose(torch.tril(C_full, diagonal=-1),1,2)
    if train_cholesky: # <- if true we don't need to reflect over the diagonal, so just return L
        return L
    else:
        return L + U

def symmetric_log(m):
    """
    Takes a a matrix and returns a piece-wise logarithm for post-processing
    sym_log(x) =  log10(x+1),  x >= 0
    sym_log(x) = -log10(-x+1), x < 0
    """
    pos_m, neg_m = torch.zeros(m.shape, device=try_gpu()), torch.zeros(m.shape, device=try_gpu())
    pos_idx = torch.where(m >= 0)
    neg_idx = torch.where(m < 0)
    pos_m[pos_idx] = m[pos_idx]
    neg_m[neg_idx] = m[neg_idx]

    pos_m[pos_idx] = torch.log10(pos_m[pos_idx] + 1)
    # for negative numbers, treat log(x) = -log(-x)
    neg_m[neg_idx] = -torch.log10(-1*neg_m[neg_idx] + 1)
    return (pos_m / 5.91572) + (neg_m / 4.62748)

def symmetric_exp(m):
    """
    Takes a matrix and returns the piece-wise exponent
    sym_exp(x) = 10^x - 1,   x > 0
    sym_exp(x) = -10^-x + 1, x < 0
    This is the reverse operation of symmetric_log
    """
    pos_m, neg_m = torch.zeros(m.shape, device=try_gpu()), torch.zeros(m.shape, device=try_gpu())
    pos_idx = torch.where(m >= 0)
    neg_idx = torch.where(m < 0)
    pos_m[pos_idx] = m[pos_idx] * 5.91572
    neg_m[neg_idx] = m[neg_idx] * 4.62748

    pos_m = 10**pos_m - 1
    pos_m[(pos_m == 1)] = 0
    # for negative numbers, treat log(x) = -log(-x)
    neg_m[neg_idx] = -10**(-1*neg_m[neg_idx]) + 1

    return pos_m + neg_m

def predict_quad(decoder_q1, decoder_q2, decoder_q3, net_f1, net_f2, net_f3, params):
    """
    takes in the feature and VAE networks for each quadrant of the matrix
    and predicts the full covariance matrix
    """
    features = net_f1(params); C_q1 = decoder_q1(features.view(1,10))
    features = net_f2(params); C_q2 = decoder_q2(features.view(1,10))
    features = net_f3(params); C_q3 = decoder_q3(features.view(1,10))
    C = torch.zeros([C_q1.shape[0], 100, 100])
    C[:,:50,:50] = C_q1
    C[:,50:,50:] = C_q2
    C[:,:50,50:] = torch.transpose(C_q3, 1, 2)
    C[:,50:,:50] = C_q3
    return C

def corr_to_cov(C):
    """
    Takes the correlation matrix + variances and returns the full covariance matrix
    NOTE: This function assumes that the variances are stored in the diagonal of the correlation matrix
    """
    # Extract the log variances from the diagaonal
    D = torch.diag_embed(torch.diag(C)).to(try_gpu())
    C = C - D + torch.eye(100).to(try_gpu())
    D = symmetric_exp(D)
    C = torch.matmul(D, torch.matmul(C, D))
    return C

def try_gpu():
    """Return gpu() if exists, otherwise return cpu()."""
    if torch.cuda.is_available():
        return torch.device('cuda:0')
    return torch.device('cpu')
