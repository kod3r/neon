# ----------------------------------------------------------------------------
# Copyright 2014 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
from neon import NervanaObject


class Cost(NervanaObject):
    """
    Base class for the cost functions
    """
    def __call__(self, y, t):
        """
        Applies the cost function

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            OpTree: Returns the cost
        """
        return self.func(y, t)

    def bprop(self, y, t):
        """
        Computes the derivative of the cost function

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            OpTree: Returns the derivative of the cost function
        """
        return self.funcgrad(y, t)


class Metric(Cost):
    """
    Base class for Metric

    Meant for non-smooth costs that we just want to check on validation.
    """
    def __call__(self, y, t):
        """
        To implement in derived classes

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            float: Returns the metric
        """
        raise NotImplementedError()

    def bprop(self, y, t):
        """
        Not relevant for Metric
        """
        pass


class CrossEntropyBinary(Cost):
    """
    Applies the binary cross entropy function

    Note:
        bprop assumes that shortcut is used to calculate derivative
    """
    def __init__(self, epsilon=2 ** -23, scale=1):
        """
        Initialize the binary cross entropy function

        Args:
            epsilon (float): set the epsilon
                             (small number to prevent log(0) errors)
        """
        self.epsilon = epsilon
        self.scale = scale

    def __call__(self, y, t):
        """
        Applies the binary cross entropy cost function

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            OpTree: Returns the binary cross entropy cost
        """
        a = - self.be.log(y + self.epsilon) * t
        b = - self.be.log(1 - y + self.epsilon) * (1 - t)
        return self.scale * self.be.sum(a + b, axis=0)

    def bprop(self, y, t):
        """
        Computes the shortcut derivative of the binary cross entropy cost function

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            OpTree: Returns the (mean) shortcut derivative of the binary entropy
                    cost function ``(y - t) / y.shape[1]``
        """
        return self.scale * (y - t) / y.shape[1]


class CrossEntropyMulti(Cost):
    """
    Applies the multiclass cross entropy function

    Note:
        bprop assumes that shortcut is used to calculate derivative
    """
    def __init__(self, epsilon=2 ** -23, scale=1, usebits=False):
        """
        Initialize the multiclass cross entropy function

        Args:
            epsilon (float): set the epsilon
                             (small number to prevent log(0) errors)
            usebits (boolean): whether to display costs in bits or nats (default)
        """
        self.epsilon = epsilon
        self.scale = scale
        self.logfunc = self.be.log2 if usebits else self.be.log

    def __call__(self, y, t):
        """
        Applies the multiclass cross entropy cost function

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            OpTree: Returns the multiclass cross entropy cost
        """
        return (self.scale *
                self.be.sum(-t * self.logfunc(self.be.clip(y, self.epsilon, 1.0)), axis=0))

    def bprop(self, y, t):
        """
        Computes the shortcut derivative of the multiclass cross entropy cost
        function

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            OpTree: Returns the (mean) shortcut derivative of the multiclass
            entropy cost function ``(y - t) / y.shape[1]``
        """
        return self.scale * (y - t) / y.shape[1]


class SumSquared(Cost):
    """
    Applies the squared error cost function
    """
    def __init__(self):
        """
        Initialize the squared error cost functions
        """
        self.func = lambda y, t: self.be.sum(
            self.be.square(y - t), axis=0) / 2.
        self.funcgrad = lambda y, t: (y - t) / y.shape[1]


class Misclassification(Metric):
    """
    Compute the misclassification error metric
    """
    def __init__(self):
        self.preds = self.be.iobuf(1)
        self.hyps = self.be.iobuf(1)
        self.outputs = self.preds  # Contains per record metric

    def __call__(self, y, t):
        """
        Compute the misclassification error metric

        Args:
            y (Tensor or OpTree): Output of previous layer or model
            t (Tensor or OpTree): True targets corresponding to y

        Returns:
            float: Returns the metric
        """
        # convert back from onehot and compare
        self.preds[:] = self.be.argmax(y, axis=0)
        self.hyps[:] = self.be.argmax(t, axis=0)
        self.outputs[:] = self.be.not_equal(self.preds, self.hyps)

        return self.outputs.get().mean()
