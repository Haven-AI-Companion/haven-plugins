import sys
import os
import json
import uuid
import urllib.request
import base64
import random

def main():
    try:
        # 1. Read stdin
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print("Error: No input arguments received.", file=sys.stderr)
            return

        # 2. Parse JSON
        args = json.loads(raw_input)
        
        description = args.get("description", "").strip()
        if not description:
            print("Error: Description argument is missing or empty.", file=sys.stderr)
            return

        # 3. Detect if full body / standing is requested
        full_body_keywords = [
            "full body", "full-body", "head to toe", "head-to-toe", "standing", 
            "legs", "feet", "boots", "shoes", "kneeling", "sitting on the floor", 
            "legs crossed", "lower body", "full length", "full-length"
        ]
        is_full_body = any(kw in description.lower() for kw in full_body_keywords)

        # Look up custom SD config from companion profile JSON
        config = args.get("config", {})
        companions_dir = config.get("server_companions_dir", r"C:\Users\admin\haven-server\personality\companions")
        sd_config = {}
        clothing_state = ""
        current_outfit = ""
        current_location = ""
        current_mood = ""
        
        if os.path.exists(companions_dir):
            # Check local override first
            local_dir = os.path.join(companions_dir, "local")
            found = False
            if os.path.exists(local_dir):
                for file_name in os.listdir(local_dir):
                    if file_name.endswith(".json"):
                        try:
                            with open(os.path.join(local_dir, file_name), "r", encoding="utf-8") as f:
                                data = json.load(f)
                                comp_name = data.get("name", "").strip()
                                if comp_name and comp_name.lower() in description.lower():
                                    sd_config = data.get("sdConfig", {})
                                    clothing_state = data.get("clothingState", "").strip().lower()
                                    current_outfit = data.get("currentOutfit", "").strip()
                                    current_location = data.get("currentLocation", "").strip()
                                    current_mood = data.get("currentMood", "").strip()
                                    print(f"[generate.py] Found LOCAL override sdConfig for {comp_name}! clothingState={clothing_state}", file=sys.stderr)
                                    found = True
                                    break
                        except Exception:
                            pass
            
            # Fallback to default companions if not found in local overrides
            if not found:
                for file_name in os.listdir(companions_dir):
                    if file_name.endswith(".json"):
                        try:
                            with open(os.path.join(companions_dir, file_name), "r", encoding="utf-8") as f:
                                data = json.load(f)
                                comp_name = data.get("name", "").strip()
                                if comp_name and comp_name.lower() in description.lower():
                                    sd_config = data.get("sdConfig", {})
                                    clothing_state = data.get("clothingState", "").strip().lower()
                                    current_outfit = data.get("currentOutfit", "").strip()
                                    current_location = data.get("currentLocation", "").strip()
                                    current_mood = data.get("currentMood", "").strip()
                                    print(f"[generate.py] Found default sdConfig override for {comp_name}! clothingState={clothing_state}", file=sys.stderr)
                                    break
                        except Exception:
                            pass

        # 4. Construct prompt with embedded seed parameter for stable-diffusion.cpp
        seed_val = random.randint(1, 2000000000)
        
        pos_prefix = sd_config.get("positive_prompt_prefix", "digital art portrait, highly detailed").strip()
        prompt_parts = [pos_prefix]
        
        # Inject custom trigger words if set in companion config
        trigger_words = sd_config.get("trigger_words", "")
        if trigger_words:
            if isinstance(trigger_words, list):
                prompt_parts.extend([tw.strip() for tw in trigger_words if tw.strip()])
            else:
                prompt_parts.append(trigger_words.strip())

        # Inject active location, outfit, and mood from companion state if not already described
        if current_outfit:
            if current_outfit.lower() not in description.lower() and current_outfit.lower() not in pos_prefix.lower():
                prompt_parts.append(f"wearing {current_outfit}")
                print(f"[generate.py] Injected active outfit: '{current_outfit}'", file=sys.stderr)

        if current_location:
            if current_location.lower() not in description.lower() and current_location.lower() not in pos_prefix.lower():
                prompt_parts.append(f"in/at {current_location}")
                print(f"[generate.py] Injected active location: '{current_location}'", file=sys.stderr)

        if current_mood:
            if current_mood.lower() not in description.lower() and current_mood.lower() not in pos_prefix.lower():
                prompt_parts.append(f"{current_mood} expression")
                print(f"[generate.py] Injected active mood: '{current_mood}'", file=sys.stderr)

        prompt_parts.append(description)
        if is_full_body:
            if "full body" not in description.lower() and "full-body" not in description.lower():
                prompt_parts.append("full body shot, standing upright, head-to-toe portrait")

        # Inject clothing state into prompt if set in companion profile
        naked_states = {"naked", "nude", "undressed", "topless", "fully nude", "fully naked", "bare"}
        if clothing_state and any(s in clothing_state for s in naked_states):
            # Only inject if not already described in the description or prefix
            already_mentioned = any(s in description.lower() or s in pos_prefix.lower() for s in naked_states)
            if not already_mentioned:
                prompt_parts.append("nude, naked, no clothes, bare skin, nudity")
                print(f"[generate.py] clothingState='{clothing_state}' -> injected nudity into prompt", file=sys.stderr)
        
        # Inject custom LoRAs if set in companion config
        loras = sd_config.get("loras", {})
        if isinstance(loras, dict):
            for lora_name, lora_weight in loras.items():
                prompt_parts.append(f"<lora:{lora_name}:{lora_weight}>")

        full_prompt = ", ".join(prompt_parts) + f"<sd_cpp_extra_args>{{\"seed\": {seed_val}}}</sd_cpp_extra_args>"

        # 5. Query the running Stable Diffusion server (loaded from plugin config)
        config = args.get("config", {})
        sd_server_url = config.get("sd_server_url", "http://127.0.0.1:8080").strip()
        sd_url = f"{sd_server_url.rstrip('/')}/v1/images/generations"

        # Determine size (vertical aspect ratio for full body reduces anatomical warping)
        widescreen_keywords = ["widescreen", "16:9", "1024x768", "1920x1080", "wallpaper", "desktop", "landscape"]
        is_widescreen = any(kw in description.lower() for kw in widescreen_keywords)

        if is_widescreen:
            size = "640x360"
        elif is_full_body:
            size = "512x768"
        else:
            size = "512x512"
        
        neg_prompt = sd_config.get("negative_prompt", "easynegative, bad-hands-5, text, watermark, bad anatomy, duplicate, split screen, multi panel, list, borders, signature, extra limbs").strip()
        if is_full_body:
            neg_prompt += ", cropped, cut off, out of frame, close up portrait, head shot"

        payload = {
            "prompt": full_prompt,
            "negative_prompt": neg_prompt,
            "n": 1,
            "size": size,
            "seed": seed_val,
            "response_format": "b64_json"
        }
        
        req = urllib.request.Request(
            sd_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        # Query local server with a 1800-second (30-minute) timeout
        with urllib.request.urlopen(req, timeout=1800) as response:
            resp_data = json.loads(response.read().decode("utf-8"))
            
        data_list = resp_data.get("data", [])
        if not data_list:
            print("Error: No image data returned from SD server", file=sys.stderr)
            return
            
        b64_string = data_list[0].get("b64_json", "")
        if not b64_string:
            print("Error: Empty b64_json returned", file=sys.stderr)
            return
            
        # 5. Save image as WebP to C:\Users\admin\haven-server\wwwroot\uploads\
        uploads_dir = r"C:\Users\admin\haven-server\wwwroot\uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        
        image_name = f"gen_{uuid.uuid4().hex}.webp"
        filepath = os.path.join(uploads_dir, image_name)
        
        import io
        from PIL import Image
        
        image_bytes = base64.b64decode(b64_string)

        if is_widescreen:
            try:
                import cv2
                import numpy as np
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    # Upscale by 2x to 1280x720 using Lanczos
                    img_upscaled = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_LANCZOS4)
                    _, encoded_img = cv2.imencode(".png", img_upscaled)
                    image_bytes = encoded_img.tobytes()
            except Exception as ex:
                print(f"Widescreen upscale error: {str(ex)}", file=sys.stderr)

        enhanced_bytes = restore_faces(image_bytes)
        
        with Image.open(io.BytesIO(enhanced_bytes)) as img:
            img.save(filepath, "WEBP", quality=80)
            
        # 6. Return the relative URL to stdout
        if os.path.exists(filepath):
            print(f"/uploads/{image_name}")
        else:
            print("Error: Output image was not created.")
            
    except Exception as e:
        print(f"Error executing generate_portrait: {str(e)}", file=sys.stderr)

def restore_faces(img_bytes):
    try:
        import cv2
        import numpy as np
        import onnxruntime as ort
        
        # Paths to models
        detector_path = r"C:\Users\admin\stable-diffusion-cpp\models\facerestore_models\face_detection_yunet_2023mar.onnx"
        gfpgan_path = r"C:\Users\admin\stable-diffusion-cpp\models\facerestore_models\GFPGANv1.4.onnx"
        
        if not os.path.exists(detector_path) or not os.path.exists(gfpgan_path):
            return img_bytes # Graceful fallback if weights not present
            
        # Decode bytes to OpenCV image
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return img_bytes
            
        h_orig, w_orig, _ = img.shape
        
        # Detect faces using YuNet
        detector = cv2.FaceDetectorYN.create(
            detector_path,
            "",
            (w_orig, h_orig),
            0.6,
            0.3,
            5000
        )
        retval, faces = detector.detect(img)
        
        if faces is None or len(faces) == 0:
            return img_bytes # No faces found, return original
            
        session = ort.InferenceSession(gfpgan_path, providers=['CPUExecutionProvider'])
        
        for face in faces:
            x, y, w, h = map(int, face[0:4])
            
            # 1.4x padding to capture chin/forehead/hair
            padding_x = int(w * 0.25)
            padding_y = int(h * 0.25)
            
            x1 = max(0, x - padding_x)
            y1 = max(0, y - padding_y)
            x2 = min(w_orig, x + w + padding_x)
            y2 = min(h_orig, y + h + padding_y)
            
            crop_w = x2 - x1
            crop_h = y2 - y1
            if crop_w < 10 or crop_h < 10:
                continue
                
            crop = img[y1:y2, x1:x2]
            crop_resized = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_LANCZOS4)
            
            # Normalize and format tensor
            crop_rgb = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            crop_norm = (crop_rgb - 0.5) / 0.5
            input_tensor = np.transpose(crop_norm, (2, 0, 1))
            input_tensor = np.expand_dims(input_tensor, axis=0)
            
            # Run GFPGAN
            outputs = session.run(["1288"], {"input": input_tensor})
            out_face = outputs[0][0]
            
            # Transpose, scale and convert back to BGR
            out_face = np.transpose(out_face, (1, 2, 0))
            out_face = (out_face * 0.5 + 0.5) * 255.0
            out_face = np.clip(out_face, 0, 255).astype(np.uint8)
            out_face_bgr = cv2.cvtColor(out_face, cv2.COLOR_RGB2BGR)
            
            out_face_resized = cv2.resize(out_face_bgr, (crop_w, crop_h), interpolation=cv2.INTER_LANCZOS4)
            
            # Radial blend mask
            center_x = crop_w // 2
            center_y = crop_h // 2
            max_dist = np.sqrt(center_x**2 + center_y**2)
            y_indices, x_indices = np.indices((crop_h, crop_w))
            dists = np.sqrt((x_indices - center_x)**2 + (y_indices - center_y)**2)
            mask = 1.0 - (dists / max_dist)
            mask = np.clip(mask * 1.5, 0.0, 1.0)
            mask = cv2.GaussianBlur(mask, (21, 21), 0)
            mask = np.expand_dims(mask, axis=2)
            
            blended = (crop.astype(np.float32) * (1.0 - mask) + out_face_resized.astype(np.float32) * mask).astype(np.uint8)
            img[y1:y2, x1:x2] = blended
            
        # Encode back to PNG/JPEG bytes
        _, encoded_img = cv2.imencode(".png", img)
        return encoded_img.tobytes()
        
    except Exception as e:
        print(f"Face restoration error: {str(e)}", file=sys.stderr)
        return img_bytes

if __name__ == "__main__":
    main()
