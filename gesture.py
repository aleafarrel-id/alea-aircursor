import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import time

class HandTracker:
    def __init__(self, cooldown=0.4, 
                 complexity=1, 
                 click_radius=20, 
                 hover_radius=25,
                 right_click_radius=50, 
                 right_hover_radius=60,
                 hold_click_radius=30, 
                 hold_hover_radius=35,
                 scroll_radius=20,
                 scroll_hover_radius=25,
                 scroll_speed=60):
        """
        Initialize the Hand Tracker with two-zone detection system (hover and click)
        and separate parameters for right-click and click-and-hold

        Args:
            cooldown (float): Delay between clicks (in seconds)
            complexity (int): MediaPipe model complexity (0, 1, or 2)
            click_radius (int): The maximum distance for left click detection (in pixel)
            hover_radius (int): The maximum distance for left hover detection (in pixel)
            right_click_radius (int): The maximum distance for right click detection (in pixel)
            right_hover_radius (int): The maximum distance for right hover detection (in pixel)
            hold_click_radius (int): The maximum distance for click-and-hold detection (in pixel)
            hold_hover_radius (int): The maximum distance for click-and-hold hover detection (in pixel)
        """
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            model_complexity=complexity,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.cooldown = cooldown
        self.click_radius = click_radius
        self.hover_radius = hover_radius
        self.right_click_radius = right_click_radius
        self.right_hover_radius = right_hover_radius
        self.hold_click_radius = hold_click_radius
        self.hold_hover_radius = hold_hover_radius
        self.last_click_time = 0
        self.last_right_click_time = 0
        self.landmark_colors = [(0, 255, 0)] * 21  # Default: Green for all landmarks
        self.tracked_landmarks = [0, 3, 4, 5, 6, 7, 8, 9, 12, 20]

        # Scroll parameters
        self.scroll_radius = scroll_radius
        self.scroll_hover_radius = scroll_hover_radius
        self.scroll_speed = scroll_speed

        # State for continuous scroll
        self.is_scrolling = False
        self.scroll_direction = None  # 'up' or 'down'
        self.last_scroll_time = 0      # Last time scroll was performed
        self.scroll_interval = 0.1     # Time interval between scroll actions

        # State for click and hold
        self.is_holding = False
        self.hold_start_time = 0
        self.hold_cooldown = 0.1  # The minimum time to be considered as hold

    def process_frame(self, frame):
        """
        Process the input frame to detect hand landmarks and perform actions based on gestures

        Args:
            frame (numpy.ndarray): Frame from the camera

        Returns:
            numpy.ndarray: Processed frame with hand landmarks drawn
        """
        # Mirror frame for better user experience
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        try:
            results = self.hands.process(rgb_frame)
        except Exception as e:
            print(f"MediaPipe processing error: {e}")
            return frame
        
        current_time = time.time()

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Reset landmark colors
                self.landmark_colors = [(0, 255, 0)] * 21

                # Extract landmark coordinates
                landmarks = []
                for idx, lm in enumerate(hand_landmarks.landmark):
                    h, w, _ = frame.shape
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    landmarks.append((cx, cy))

                # Move cursor based on index finger position (8th landmark)
                if len(landmarks) > 8:
                    index_tip = landmarks[8]
                    screen_w, screen_h = pyautogui.size()
                    cursor_x = np.interp(index_tip[0], [0, w], [0, screen_w])
                    cursor_y = np.interp(index_tip[1], [0, h], [0, screen_h])
                    pyautogui.moveTo(cursor_x, cursor_y, _pause=False)

                # Scroll detection (up or down)
                self.detect_scroll(landmarks, current_time)

                # Click and hold detection (OK gesture)
                self.detect_click_and_hold(landmarks, current_time)

                # Left click detection
                if not self.is_holding and self.detect_thumb_index_contact(landmarks, current_time):
                    pyautogui.click()

                # Right click detection
                if self.detect_pinky_wrist_contact(landmarks, current_time):
                    pyautogui.rightClick()

                # Draw landmarks with colors
                self.draw_points_only(frame, landmarks)
        else:
            # If no hands detected, reset states
            if self.is_holding:
                pyautogui.mouseUp()
                self.is_holding = False

        return frame
    
    def detect_scroll(self, landmarks, current_time):
        """
        Detect scroll gesture using index and middle finger landmarks
        """
        if len(landmarks) < 13:  # Make sure we have enough landmarks (12, 8)
            if self.is_scrolling:
                self.is_scrolling = False
            return
        
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        middle_base = landmarks[9]  # Base of middle finger for scroll direction
        
        # Calculate distance between index and middle finger tips
        distance = np.linalg.norm(np.array(index_tip) - np.array(middle_tip))
        
        # Calculate vertical difference for scroll direction
        mid_y = (index_tip[1] + middle_tip[1]) // 2
        vertical_diff = mid_y - middle_base[1]
        direction = 'up' if vertical_diff < -15 else 'down' if vertical_diff > 15 else None

        # Hover scroll zone
        if distance < self.scroll_hover_radius:
            self.landmark_colors[8] = (0, 255, 255)  # Yellow for hover
            self.landmark_colors[12] = (0, 255, 255)
            self.landmark_colors[9] = (0, 255, 255)

            # Active scroll zone
            if distance < self.scroll_radius and direction:
                self.landmark_colors[8] = (255, 0, 255)  # Magenta for active scroll
                self.landmark_colors[12] = (255, 0, 255)
                self.landmark_colors[9] = (255, 0, 255)
                
                # If not already scrolling, start scrolling
                if not self.is_scrolling:
                    self.is_scrolling = True
                    self.scroll_direction = direction
                    self._perform_scroll()
                    self.last_scroll_time = current_time
                
                # If already scrolling, check if we need to change direction or continue
                elif current_time - self.last_scroll_time > self.scroll_interval:
                    # Update scroll direction if it has changed
                    if direction != self.scroll_direction:
                        self.scroll_direction = direction
                    self._perform_scroll()
                    self.last_scroll_time = current_time
            else:
                # If in hover zone but not active scroll, stop scrolling
                if self.is_scrolling:
                    self.is_scrolling = False
        else:
            # If distance is too far, stop scrolling
            if self.is_scrolling:
                self.is_scrolling = False
    
    def _perform_scroll(self):
        """Perform the actual scroll action based on the current direction"""
        scroll_amount = self.scroll_speed if self.scroll_direction == 'up' else -self.scroll_speed
        pyautogui.scroll(scroll_amount)


    def detect_click_and_hold(self, landmarks, current_time):
        """
        Detect click-and-hold gesture using thumb and index finger landmarks (OK gesture)

        Args:
            landmarks (list): Coordinates of hand landmarks
            current_time (float): Current time for cooldown management
        """
        if len(landmarks) < 9:
            return

        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        distance = np.linalg.norm(np.array(thumb_tip) - np.array(index_tip))

        # Hover zone for click-and-hold
        if distance < self.hold_hover_radius:
            self.landmark_colors[4] = (0, 255, 255)  # Yellow for hover
            self.landmark_colors[8] = (0, 255, 255)

            # Active zone for click-and-hold
            if distance < self.hold_click_radius:
                self.landmark_colors[4] = (0, 0, 255)  # Red for active click-and-hold
                self.landmark_colors[8] = (0, 0, 255)

                # If not already holding, start holding
                if not self.is_holding:
                    self.hold_start_time = current_time
                    self.is_holding = True
                    pyautogui.mouseDown()
                # If already holding, check if we need to continue holding
                else:
                    # Check if we are still within the hold cooldown period
                    if current_time - self.hold_start_time > self.hold_cooldown:
                        pass # Holding continues
            else:
                # If in hover zone but not active hold, release hold
                if self.is_holding:
                    pyautogui.mouseUp()
                    self.is_holding = False
        else:
            # If distance is too far, release hold
            if self.is_holding:
                pyautogui.mouseUp()
                self.is_holding = False

    def detect_thumb_index_contact(self, landmarks, current_time):
        """
        Detect contact between thumb and index finger for left click using two-zone system

        Args:
            landmarks (list): Coordinates of hand landmarks
            current_time (float): Current time for cooldown management

        Returns:
            bool: True if left click is detected, False if not
        """
        if (len(landmarks) < 9 or
            current_time - self.last_click_time < self.cooldown or
            self.is_holding):  # Skip if holding
            return False

        thumb_tip = landmarks[4]
        contact_detected = False

        # Check contact between thumb and index finger
        for idx in [5, 6, 7, 8]:
            distance = np.linalg.norm(np.array(thumb_tip) - np.array(landmarks[idx]))

            # Hover zone (almost touching)
            if distance < self.hover_radius:
                self.landmark_colors[4] = (0, 255, 255)  # Yellow
                self.landmark_colors[idx] = (0, 255, 255)

                # Click zone (actually touching)
                if distance < self.click_radius:
                    self.landmark_colors[4] = (255, 0, 0)  # Blue
                    self.landmark_colors[idx] = (255, 0, 0)
                    contact_detected = True

        if contact_detected:
            self.last_click_time = current_time
            return True

        return False

    def detect_pinky_wrist_contact(self, landmarks, current_time):
        """
        Detect contact between pinky finger and wrist for right click using two-zone system

        Args:
            landmarks (list): Coordinates of hand landmarks
            current_time (float): Current time for cooldown management

        Returns:
            bool: True if right click is detected, False if not
        """
        if (len(landmarks) < 21 or
            current_time - self.last_right_click_time < self.cooldown):
            return False

        pinky_tip = landmarks[20]
        wrist = landmarks[0]
        distance = np.linalg.norm(np.array(pinky_tip) - np.array(wrist))

        # Hover zone for right click
        if distance < self.right_hover_radius:
            self.landmark_colors[20] = (0, 255, 255)  # Yellow
            self.landmark_colors[0] = (0, 255, 255)

            # Click zone for right click
            if distance < self.right_click_radius:
                self.landmark_colors[20] = (255, 0, 0)  # Blue
                self.landmark_colors[0] = (255, 0, 0)
                self.last_right_click_time = current_time
                return True

        return False

    def draw_points_only(self, frame, landmarks):
        """
        Draw only the tracked landmarks on the frame

        Args:
            frame (numpy.ndarray): Frame to draw landmarks on
            landmarks (list): Coordinates of hand landmarks
        """
        for idx in self.tracked_landmarks:
            if idx < len(landmarks):
                cx, cy = landmarks[idx]
                color = self.landmark_colors[idx]
                cv2.circle(frame, (cx, cy), 6, color, -1)

    def release(self):
        """
        Release resources when done
        """
        self.hands.close()