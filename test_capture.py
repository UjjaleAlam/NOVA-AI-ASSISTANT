from PIL import Image

# Open the original image
img = Image.open('!base.png')

# Define the coordinates for the top-left logo (Left, Top, Right, Bottom)
# Note: These are approximate pixel coordinates based on the image provided
crop_area = (20, 20, 415, 125) 

# Crop and save the image
logo = img.crop(crop_area)
logo.save('extracted_logo.png')
print("Logo extracted successfully!")