from PIL import Image, ExifTags
import numpy as np
import pandas as pd
import numpy.matlib
import plotly.express as px
import base64
import re
import os
from os.path import isfile
# pip install -U kaleido


def myRange(start, end, step):
    i = start
    while i < end:
        yield i
        i += step
    yield end


def get_skyline(encoded_image, encoded_mask):
    # encoded_image=data['sensors'][0]['image']
    base64_image = re.sub('^data:image/.+;base64,', '', encoded_image)

    with open("image.png", "wb") as fh:
        fh.write(base64.b64decode(base64_image))

    decoded_image = np.asarray(Image.open("image.png"))

    # encoded_mask=data['sensors'][0]['png']
    base64_mask = re.sub('^data:image/.+;base64,', '', encoded_mask)
    with open("masks.png", "wb") as fh:
        fh.write(base64.b64decode(base64_mask))
    decoded_mask = np.asarray(Image.open("masks.png"))

    height, width = decoded_image.shape[:-1]
    haov = 50
    vaov = 45

    h_weight = width/haov
    v_weight = height/vaov

    masks = np.bitwise_or(
        np.bitwise_or(
            decoded_mask[:, :, 0].astype(np.uint32),
            decoded_mask[:, :, 1].astype(np.uint32) << 8
        ),
        decoded_mask[:, :, 2].astype(np.uint32) << 16)

    dataset = {
        "labels": ["background", "sky", "trees"],
        "imageURLs": ["image.png"],
        "annotationURLs": ["masks.png"]
    }

    output = {}
    for label in dataset['labels']:
        output[label] = []

    for ix, iy in np.ndindex(masks.shape):
        map = masks[ix, iy]
        labels = list(output.keys())
        key = labels[map]
        output[key].append({'x': ix, 'y': iy})

    mapping = np.zeros(decoded_image.shape[:-1])

    for k in output.keys():
        for i in output[k]:
            if k == 'background':
                mapping[i['x'], i['y']] = 0
            elif k == 'trees':
                mapping[i['x'], i['y']] = 0
            elif k == 'sky':
                mapping[i['x'], i['y']] = 1

    height_indices = list(myRange(0, height-1, np.int(h_weight)))
    width_indices = list(range(0, width-1, np.int(v_weight)))

    group = np.zeros([len(height_indices)-1, len(width_indices)-1])

    for i in range(len(height_indices)-1):
        for j in range(len(width_indices)-1):
            sum = np.sum(
                mapping[height_indices[i]:height_indices[i+1], width_indices[j]:width_indices[j+1]])
            if sum == (height_indices[i+1]-height_indices[i])*(width_indices[j+1]-width_indices[j]):
                group[i, j] = 1
            else:
                group[i, j] = 0

    center_azimuth = 100  # alpha
    center_elevation = 40  # beta

    # center_azimuth=np.int(np.round(np.float(data['sensors'][1]['orientation']['alpha'])))
    # center_elevation=np.int(np.round(np.float(data['sensors'][1]['orientation']['beta'])))

    skyline = np.zeros([91, 360])
    skyline[center_elevation - np.int(np.floor(group.shape[0]/2)): center_elevation + np.int(np.ceil(group.shape[0]/2)),
            center_azimuth - np.int(np.floor(group.shape[1]/2)): center_azimuth + np.int(np.ceil(group.shape[1]/2))] = np.flip(group, (0))

    skyline = skyline.transpose()
    skyline_dict = {}

    for i in range(len(skyline)):
        skyline_dict[i] = skyline[i]
    # print(skyline_dict)

    azimuth_series = pd.Series(
        np.repeat(np.array(range(360)), 91), dtype='int16')
    elevation_series = pd.Series(numpy.matlib.repmat(
        np.array(range(91)), 1, 360)[0], dtype='int8')
    skyline_series = pd.Series([item for sublist in list(
        skyline) for item in sublist], dtype='int8')

    skyline_df = pd.DataFrame({'azimuth': azimuth_series,
                               'elevation': elevation_series,
                               'skyline': skyline_series})

    fig = px.scatter(skyline_df, x="azimuth", y="elevation", color="skyline")
    fig.write_image("skyline.png")

    with open("skyline.png", "rb") as img_file:
        skyline_b64_bytes = base64.b64encode(img_file.read())

        ### Decode image data from bytes to string
        skyline_b64_string = skyline_b64_bytes.decode()

        ### Format the base64 image to a data-uri format usable in html/css
        skyline_b64_string = 'data:image/png;base64,{}'.format(
            skyline_b64_string)

    # *****************************************
    # ****** Remove temp image files
    # *****************************************
    if isfile('image.png'):
        os.remove('image.png')

    if isfile('masks.png'):
        os.remove('masks.png')

    if isfile('skyline.png'):
        os.remove('skyline.png')

    return skyline_b64_string
