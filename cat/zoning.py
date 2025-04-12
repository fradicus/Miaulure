import cv2

cap = cv2.VideoCapture(0)


print("Press 's' to save a picture or 'q' to quit.")


while True:
    # Capture a frame from the webcam
    picWorked, frame = cap.read()
    if not picWorked:
        print("Error: Could not read frame from webcam.")
        break

   

    # Display the frame with gridlines
    cv2.imshow("Webcam with Gridlines", frame)

    # Wait for a key press
    key = cv2.waitKey(1) & 0xFF

    if key == ord("s"):  
        file_path = r"C:\Users\Elizabeth\Desktop\MEOW\Zoning.jpg"
        cv2.imwrite(file_path, frame)
        print(f"Image saved to {file_path}")

    elif key == ord("q"): 
        print("Exiting program.")
        break

# Release the webcam and close all OpenCV windows
cap.release()
cv2.destroyAllWindows()

