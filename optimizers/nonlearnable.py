from .base import OptimizerBase
from degradations import DegradationBase
from typing import Tuple, Callable, Dict, Any
import torch as th
import torch.nn as nn


class TorchGradientOptimizer(OptimizerBase):
    """
    This class implements optimization using standard PyTorch optimizers.
    """
    optimizer: Callable
    num_steps: int
    optimizer_hyperparams: Dict[str, Any]

    def __init__(self, degradation: DegradationBase, num_steps: int, prior_function: Callable, prior_weight: float,
                 projection_function: Callable, optimizer: th.optim.Optimizer, **optimizer_kwargs) -> None:
        """
        Initializing all instances, required for optimization.

        :param degradation: function, which provides degradation model
        :param num_steps: number of optimizer steps to perform for restoration
        :param prior_function: function, which is called to calculate images priors
        :param prior_weight: regularization weight to scale the prior value properly (usually is as hyperparameter)
        :param projection_function: function, which is called to explicitly project images to some specific domain
        """
        super().__init__(degradation, num_steps, prior_function, prior_weight, projection_function)
        self.optimizer = optimizer
        self.optimizer_hyperparams = optimizer_kwargs

    def _initialize_params(self, images: th.Tensor) -> nn.Parameter:
        """
        Method, which casts input tensor to nn.Parameter to perform optimization on it.

        :param images: input tensor to be casted to nn.Parameter
        :return: nn.Parameter with data, given by input tensor
        """
        param_images = nn.Parameter(images)
        param_images.requires_grad = True
        return param_images

    def _initialize_optimizer(self, images: nn.Parameter) -> th.optim.Optimizer:
        """
        Method, which initializes PyTorch optimizer with required params and hyperparams.

        :param images: input tensor, casted to nn.Parameter, which should be optimized
        :return: PyTorch optimizer, initialized for images
        """
        optimizer = self.optimizer([images], **self.optimizer_hyperparams)
        return optimizer

    def perform_step(self, latent_images: nn.Parameter, degraded_images: th.Tensor,
                     optimizer: th.optim.Optimizer) -> th.Tensor:
        """
        This method perfomrs a minimization step on objective, using PyTorch autograd mechanics and PyTorch optimizer.
        Here it is assumed, that input tensor was already casted to nn.Parameter and to self.optimizer was initialized.

        :param latent_images: batch of current images estimates of shape [B, C1, H1, W1], wrapped with nn.Parameter
        :param degraded_images: batch of degraded of shape [B, C2, H2, W2]
        :param optimizer: PyTorch optimizer, which should perform optimization steps
        :return: nn.Parameter with updated latent images of shape [B, C1, H1, W1]
        """
        def closure():
            if th.is_grad_enabled():
                optimizer.zero_grad()
            loss = self.objective(latent_images, degraded_images)
            if loss.requires_grad:
                loss.backward()
            return loss
        optimizer.step(closure)
        return latent_images

    def restore(self, degraded_images: th.Tensor) -> th.Tensor:
        """
        Restore input degraded images, evaluating PyTorch optimizer on objective, constructed as a sum of likelihood
        and prior values.

        :param degraded_images: batch of degraded images of shape [B, C, H, W] needed for restoration
        :return: restored images of shape [B, C, H, W]
        """
        latent_images = self.degradation.init_latent_images(degraded_images)
        latent_images = self._initialize_params(latent_images)
        optimizer = self._initialize_optimizer(latent_images)
        for i in range(self.num_steps):
            self.perform_step(latent_images, degraded_images, optimizer)
            latent_images.data = self.project(latent_images.data)
        return latent_images.data
