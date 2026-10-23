import numpy as np

from minieyes_detector.preprocess import letterbox


def frame(width, height, bgr=(0, 0, 0)):
    return np.full((height, width, 3), bgr, dtype=np.uint8)


def test_wide_frame_is_scaled_to_fit_and_padded_top_and_bottom():
    _, transform = letterbox(frame(1280, 720))

    assert transform.scale == 0.5
    assert (transform.pad_x, transform.pad_y) == (0, 140)


def test_output_is_a_normalised_nchw_float_tensor():
    tensor, _ = letterbox(frame(1280, 720, bgr=(255, 255, 255)))

    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert tensor.min() >= 0.0 and tensor.max() == 1.0


def test_channels_are_converted_from_bgr_to_rgb():
    pure_blue = frame(640, 640, bgr=(255, 0, 0))

    tensor, _ = letterbox(pure_blue)

    red, green, blue = tensor[0, :, 320, 320]
    assert (red, green, blue) == (0.0, 0.0, 1.0)


def test_model_space_box_maps_back_to_original_frame_pixels():
    _, transform = letterbox(frame(1280, 720))

    # worked example: original (400, 200, 800, 600) -> x*0.5, y*0.5 + 140 in model space
    assert transform.to_original((200, 240, 400, 440)) == (400, 200, 800, 600)
