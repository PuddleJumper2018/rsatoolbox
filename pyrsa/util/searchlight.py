#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This code was initially inspired by the following :
https://github.com/machow/pysearchlight

@author: Daniel Lindh
"""
import numpy as np
from scipy.spatial.distance import cdist
from tqdm import tqdm
from joblib import Parallel, delayed
from pyrsa.data.dataset import Dataset
from pyrsa.rdm.calc import calc_rdm
from pyrsa.rdm import RDMs


def _get_searchlight_neighbors(mask, center, radius=3):
    """Return indices for searchlight where distance
        between a voxel and their center < radius (in voxels)

    Args:
        center (index):  point around which to make searchlight sphere

    Returns:
        list: the list of volume indices that respect the
                searchlight radius for the input center.
    """
    center = np.array(center)
    mask_shape = mask.shape
    c_x, c_y, c_z = np.array(center)
    x = np.arange(mask_shape[0])
    y = np.arange(mask_shape[1])
    z = np.arange(mask_shape[2])

    # First mask the obvious points
    # - may actually slow down your calculation depending.
    x = x[abs(x - c_x) < radius]
    y = y[abs(y - c_y) < radius]
    z = z[abs(z - c_z) < radius]

    # Generate grid of points
    X, Y, Z = np.meshgrid(x, y, z)
    data = np.vstack((X.ravel(), Y.ravel(), Z.ravel())).T
    distance = cdist(data, center.reshape(1, -1), 'euclidean').ravel()

    return tuple(data[distance < radius].T.tolist())


def get_volume_searchlight(mask, radius=2, threshold=1.0):
    """Searches through the non-zero voxels of the mask, selects centers where
        proportion of sphere voxels >= self.threshold.

    Args:
        mask ([numpy array]): binary brain mask
        radius (int, optional): the radius of each searchlight,
            defined in voxels. Defaults to 2.
        threshold (float, optional):
            Threshold of the proportion of voxels that need to
            be inside the brain mask in order for it to be
            considered a good searchlight center.
            Values go between 0.0 - 1.0 where 1.0 means that
            100% of the voxels need to be inside
            the brain mask. Defaults to 1.0.

    Returns:
        [numpy array]: array of centers of size n_centers x 3
        [list]: list of lists with neighbors
            the length of the list will correspond to:
                n_centers x 3 x n_neighbors
    """

    mask = np.array(mask)
    assert mask.ndim == 3, "Mask needs to be a 3-dimensional numpy array"

    centers = list(zip(*np.nonzero(mask)))
    good_centers = []
    good_neighbors = []

    for center in tqdm(centers, desc='Finding searchlights...'):
        neighbors = _get_searchlight_neighbors(mask, center, radius)
        if mask[neighbors].mean() >= threshold:
            good_centers.append(center)
            good_neighbors.append(neighbors)

    good_centers = np.array(good_centers)
    assert good_centers.shape[0] == len(good_neighbors),\
        "number of centers and sets of neighbors do not match"
    print(f'Found {len(good_neighbors)} searchlights')

    # turn the 3-dim coordinates to array coordinates
    centers = np.ravel_multi_index(good_centers.T, mask.shape)
    neighbors = [np.ravel_multi_index(n, mask.shape) for n in good_neighbors]

    return centers, neighbors


def get_searchlight_rdms(data_2d, centers, neighbors, events,
                         method='correlation'):
    """Iterates over all the searchlight centers and calculates the rdm

    Args:
        data_2d (2D numpy array): brain data
            shape n_observations x n_channels (i.e. voxels/vertices)
        centers (1D numpy array): center indices for all searchlights
            as provided by pyrsa.util.searchlight.get_volume_searchlight
        neighbors (list): list of lists with neighbor voxel indices
            for all searchlights
            as provided by pyrsa.util.searchlight.get_volume_searchlight
        events (1D numpy array): 1D array of length n_observations
        method (str, optional): distance metric,
            see pyrsa.rdm.calc for options. Defaults to 'correlation'.

    Returns:
        rdm [pyrsa.rdm.RDMs]:
            RDMs object with the rdm for each searchlight
            the rdm.rdm_descriptors['voxel_index']
            describes the center voxel index each rdm is associated with
    """

    data_2d, centers = np.array(data_2d), np.array(centers)
    n_centers = centers.shape[0]

    # For memory reasons, we chunk the data if we have more than 1000 RDMs
    if n_centers > 1000:
        # we can't run all centers at once, that will take too much memory
        # so lets to some chunking
        chunked_center = np.split(np.arange(n_centers),
                                  np.linspace(0, n_centers,
                                              101, dtype=int)[1:-1])

        # loop over chunks
        n_conds = len(np.unique(events))
        rdm = np.zeros((n_centers, n_conds * (n_conds - 1) // 2))
        for chunk in tqdm(chunked_center, desc='Calculating RDMs...'):
            center_data = []
            for i_c in chunk:
                # grab this center and neighbors
                center = centers[i_c]
                center_neighbors = neighbors[i_c]
                # create a database object with this data
                dataset = Dataset(
                    data_2d[:, center_neighbors],
                    descriptors={'center': center},
                    obs_descriptors={'events': events},
                    channel_descriptors={'voxels': center_neighbors})
                center_data.append(dataset)

            rdm_corr = calc_rdm(center_data, method=method,
                                descriptor='events')
            rdm[chunk, :] = rdm_corr.dissimilarities
    else:
        center_data = []
        for i_c in range(n_centers):
            # grab this center and neighbors
            center = centers[i_c]
            voxels = neighbors[i_c]
            # create a database object with this data
            dataset = Dataset(
                data_2d[:, voxels],
                descriptors={'center': i_c},
                obs_descriptors={'events': events},
                channel_descriptors={'voxels': voxels})
            center_data.append(dataset)
        # calculate RDMs for each database object
        rdm = calc_rdm(center_data, method=method,
                       descriptor='events').dissimilarities

    sl_rdms = RDMs(rdm,
                   rdm_descriptors={'voxel_index': centers},
                   dissimilarity_measure=method)

    return sl_rdms


def evaluate_models_searchlight(sl_rdm, models, eval_function, method='corr',
                                theta=None, n_jobs=1):
    """evaluates each searchlighth with the given model/models

    Args:
        sl_rdm ([pyrsa.rdm.RDMs]): RDMs object
            as computed by pyrsa.util.searchlight.get_searchlight_rdms
        models ([pyrsa.model]: models to evaluate - can also be list of models
        eval_function (pyrsa.inference evaluation-function): [description]
        method (str, optional): see pyrsa.rdm.compare for specifics.
            Defaults to 'corr'.
        n_jobs (int, optional): how many jobs to run. Defaults to 1.

    Returns:
        [list]: list of with the model evaluation for each searchlight center
    """

    results = Parallel(n_jobs=n_jobs)(
        delayed(eval_function)(
            models, x, method=method, theta=theta) for x in tqdm(
            sl_rdm, desc='Evaluating models for each searchlight'))

    return results
