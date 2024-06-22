import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torchvision import datasets, transforms
import cv2 as cv
import argparse
from icecream import ic
import numpy as np
from torch.optim.lr_scheduler import StepLR
import os

device = 'cpu'
if torch.cuda.is_available():
    device = "cuda"
elif torch.backends.mps.is_available():
    device = "mps"


class Net(nn.Module):
    
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, 1)
        self.conv2 = nn.Conv2d(32, 64, 3, 1)
        self.conv3 = nn.Conv2d(64, 128, 3, 1)
        self.conv4 = nn.Conv2d(128, 512, 3, 1)
        self.conv5 = nn.Conv2d(512, 1024, 3, 1)
        self.dropout1 = nn.Dropout(0.25)
        self.dropout2 = nn.Dropout(0.50)
        self.dropout3 = nn.Dropout(0.75)
        self.ln1 = nn.Linear(7*7*1024, 1024)   
        self.ln2 = nn.Linear(1024, 128)
        self.ln3 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = F.relu(x)
        x = self.conv2(x)
        x = F.relu(x)
        x = self.conv3(x)
        x = F.relu(x)
        x = F.max_pool2d(x, 2)
        x = self.conv4(x)
        x = F.relu(x)
        x = self.conv5(x)
        x = F.relu(x)
        x = self.dropout1(x)
        x = torch.flatten(x, 1)
        x = self.ln1(x)
        x = F.relu(x)
        x = self.dropout2(x)
        x = self.ln2(x)
        x = F.relu(x)
        x = self.dropout3(x)
        x = self.ln3(x)
        return x
        

def get_dataset(B):
    dataset_train = datasets.MNIST("../data", train=True, transform=transforms.ToTensor(), download=True)
    dataset_test = datasets.MNIST("../data", train=False, transform=transforms.ToTensor())
    
    train_loader = torch.utils.data.DataLoader(dataset_train, B, shuffle=True)
    test_loader = torch.utils.data.DataLoader(dataset_test, B, shuffle=True)
    
    return train_loader, test_loader


def train(model, device, train_loader, optimizer, epoch):
    model.train()
    for batch_idx, (x, y) in enumerate(train_loader):
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        logits = model(x)  # feedforward
        loss = F.cross_entropy(logits, y)
        loss.backward()  # backpropagation
        optimizer.step()
        if batch_idx % 10 == 0:
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch, batch_idx * len(x), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item()))

        
def val(model, device, test_loader):
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for x, y in test_loader:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            test_loss += F.cross_entropy(logits, y)
            pred = logits.argmax(dim=1, keepdim=True)  # get the index of the max log-probability
            correct += pred.eq(y.view_as(pred)).sum().item()
    test_loss /= len(test_loader.dataset)
    print(f"Val Loss: {test_loss:.4f}  |  Accuracy: {correct}/{len(test_loader.dataset)}")


def infer(model, device, image):
    model.to(device)
    results = model(image)
    return results


def preprocess(image_path: str):
    image = cv.imread(image_path, 0)
    image = cv.bitwise_not(image)
    image = cv.copyMakeBorder(image, 2, 2, 2, 2, cv.BORDER_CONSTANT, value=0)
    image = cv.resize(image, (28, 28))
    # image.imshow()
    image = image.astype(np.float32)
    image = image / 255
    ic(image.shape)
    image = np.expand_dims(image, axis=0)
    ic(image.shape)
    image = np.expand_dims(image, axis=0)
    ic(image.shape)   # batch, channel, height, width
    image = torch.from_numpy(image)
    return image


def postprocess(results):
    results = torch.Tensor.detach(results)
    results = torch.Tensor.numpy(results)
    return np.argmax(results)


def main():
    parser = argparse.ArgumentParser(description='PyTorch MNIST Example')
    parser.add_argument("-b", "--num-batch", type=int, default=32, help="Number of batches")
    parser.add_argument("-p", "--image-path", type=str, help="Path to test image")
    parser.add_argument("--epochs", type=int, default=10, help="Number of Epochs")
    parser.add_argument("-lr", "--learning-rate", type=float, default=2e-3,help="Leaning rate of the Net")
    parser.add_argument("--gamma", type=float, default=0.7, help="Leaning rate step")
    parser.add_argument("--compile", action="store_true", default=False, help="Compile the model")
    parser.add_argument("--load-model", action="store_true", default=False, help="Load a pre-trained model")
    parser.add_argument("--save-model", action="store_true", default=False, help="Save after training")
    parser.add_argument("-v", '--verbose', action="store_true", default=False, help='Prints everything')

    args = parser.parse_args()

    if args.verbose:
        ic.enable()
    else:
        ic.disable()
        
    train_loader, test_loader = get_dataset(args.num_batch)

    model = Net()
    if args.load_model:
        try:
            model.load_state_dict(torch.load("mnist_cnn.pt", map_location=device))
        except FileNotFoundError:
            print("Couldn't find the pre-trained model.")
            print("Try training one, or check the path.")
        except Exception as e:
            print(f"Error: {e}")

        model = model.to(device)
        if args.compile:
            model = torch.compile(model)
        model.eval()
        
    else:
        model = model.to(device)
        optimizer = optim.Adadelta(model.parameters(), lr=args.learning_rate)
        
        if args.compile:
            model = torch.compile(model)
        
        scheduler = StepLR(optimizer, step_size=1, gamma=args.gamma)
        for epoch in range(1, args.epochs + 1):
            train(model, device, train_loader, optimizer, epoch)
            val(model, device, test_loader)
            scheduler.step()

    if args.image_path != None:
        image = preprocess(args.image_path).to(device)
        result = infer(model, device, image)
        result = postprocess(result)
        print(f"Result for the image '{args.image_path}': {result}")

    if args.save_model:
        try:
            torch.save(model.state_dict(), "./model/mnist_cnn.pt")  # pt, safer than pth
        except Exception as e:
            print(f"Error {e}")


if __name__ == '__main__':
    main()