import cv2
import torch
import base64
import numpy as np
from PIL import Image
from io import BytesIO
from diffusers.utils import load_image
from diffusers import UniPCMultistepScheduler, StableDiffusionControlNetPipeline, ControlNetModel
from potassium import Potassium, Request, Response

app = Potassium("my_app")


@app.init
def init():
    controlnet = ControlNetModel.from_pretrained(
        "lllyasviel/sd-controlnet-canny", torch_dtype=torch.float16)
    model = StableDiffusionControlNetPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        controlnet=controlnet,
        safety_checker=None,
        torch_dtype=torch.float16)
    context = {
        "model": model,
        "controlnet": controlnet,
    }

    return context


@app.handler()
def handler(context: dict, request: Request) -> Response:
    model_inputs = request.json
    model = context.get("model")
    controlnet = context.get("controlnet")
    outputs = inference(model, controlnet, model_inputs)

    return Response(json={"outputs": outputs}, status=200)


# Inference is ran for every server call
# Reference your preloaded global model variable here.


def inference(model, controlnet, model_inputs: dict) -> dict:

    # Parse out your arguments
    prompt = model_inputs.get('prompt', None)
    negative_prompt = model_inputs.get('negative_prompt', None)
    num_inference_steps = model_inputs.get('num_inference_steps', 20)
    image_data = model_inputs.get('image_data', None)
    if prompt == None:
        return {'message': "No prompt provided"}

    # Run the model
    image = Image.open(BytesIO(base64.b64decode(image_data))).convert("RGB")
    image = np.array(image)
    low_threshold = 100
    high_threshold = 200
    image = cv2.Canny(image, low_threshold, high_threshold)
    image = image[:, :, None]
    image = np.concatenate([image, image, image], axis=2)

    canny_image = Image.fromarray(image)
    buffered = BytesIO()
    canny_image.save(buffered, format="JPEG")
    canny_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    model.scheduler = UniPCMultistepScheduler.from_config(
        model.scheduler.config)
    model.enable_model_cpu_offload()
    model.enable_xformers_memory_efficient_attention()
    output = model(prompt,
                   canny_image,
                   negative_prompt=negative_prompt,
                   num_inference_steps=20)

    image = output.images[0]
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # Return the results as a dictionary
    return {'canny_base64': canny_base64, 'image_base64': image_base64}

if __name__ == "__main__":
    app.serve()