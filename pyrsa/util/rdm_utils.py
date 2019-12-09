#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collection of helper methods for rdm module
    batch_to_vectors:  batch squareform() to vectors
    batch_to_matrices: batch squareform() to matrices
@author: baihan
"""

import numpy as np
from scipy.spatial.distance import squareform


def batch_to_vectors(x):
    """
    converts a *stack* of RDMs in vector or matrix form into vector form

        Args:
            x(np.ndarray): stack of RDMs

        Returns:
            v(np.ndarray):
                2D, vector form of the stack of RDMs
            n_rdm(int):
                number of rdms
            n_cond(int)
                number of conditions
    """
    if x.ndim == 2:
        v = x
        n_rdm = x.shape[0]
        n_cond = get_n_from_reduced_vectors(x)
    elif x.ndim == 3:
        m = x
        n_rdm = x.shape[0]
        n_cond = x.shape[1]
        v = np.ndarray((n_rdm, int(n_cond * (n_cond - 1) / 2)))
        for idx in np.arange(n_rdm):
            v[idx, :] = squareform(m[idx, :, :], checks=False)
    return v, n_rdm, n_cond


def batch_to_matrices(x):
    """
    converts a *stack* of RDMs in vector or matrix form into matrix form

        Args:
            x(np.ndarray): stack of RDMs

        Returns:
            v(np.ndarray):
                3D, matrix form of the stack of RDMs
            n_rdm(int):
                number of rdms
            n_cond(int):
                number of conditions
    """
    if x.ndim == 2:
        v = x
        n_rdm = x.shape[0]
        n_cond = get_n_from_reduced_vectors(x)
        m = np.ndarray((n_rdm, n_cond, n_cond))
        for idx in np.arange(n_rdm):
            m[idx, :, :] = squareform(v[idx, :])
    elif x.ndim == 3:
        m = x
        n_rdm = x.shape[0]
        n_cond = x.shape[1]
    return m, n_rdm, n_cond


def get_n_from_reduced_vectors(x):
    """
    calculates the size of the RDM from the vector representation

        Args:
            x(np.ndarray): stack of RDM vectors (2D)

        Returns:
            n(int): size of the RDM
    """
    return int(np.ceil(np.sqrt(x.shape[1] * 2)))


def check_equal_dimension(rdm1, rdm2):
    """
    raises an error if the two RDMs objects have different dimensions

        Args:
            rdm1 (pyrsa.rdm.RDMs):
                first set of RDMs
            rdm2 (pyrsa.rdm.RDMs):
                second set of RDMs
    """
    vector1 = rdm1.get_vectors()
    vector2 = rdm2.get_vectors()
    if not vector1.shape[1] == vector2.shape[1]:
        raise ValueError('rdm1 and rdm2 must be RDMs of equal shape')
