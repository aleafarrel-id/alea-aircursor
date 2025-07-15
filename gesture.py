import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import time
import platform
import threading

pyautogui.FAILSAFE = False

class HandTracker:
    def __init__(self, cooldown=0.4, 
                 complexity=1, 
                 click_radius=20, 
                 hover_radius=25,
                 right_click_radius=50, 
                 right_hover_radius=60,
                 hold_click_radius=30, 
                 hold_hover_radius=35,
                 scroll_radius=25,
                 scroll_hover_radius=30,
                 scroll_speed=60):
        """
        Initialize the Hand Tracker with Windows and Linux support only
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
        self.landmark_colors = [(0, 255, 0)] * 21
        self.tracked_landmarks = [0, 3, 4, 5, 6, 7, 8, 9, 12, 20]

        # Scroll parameters
        self.scroll_radius = scroll_radius
        self.scroll_hover_radius = scroll_hover_radius
        self.scroll_speed = scroll_speed

        # State for continuous scroll
        self.is_scrolling = False
        self.scroll_direction = None
        self.last_scroll_time = 0
        self.scroll_interval = 0.1
        
        # Thread for smooth scrolling
        self.scroll_thread = None
        self.scroll_active = False
        self.scroll_lock = threading.Lock()

        # State for click and hold
        self.is_holding = False
        self.hold_start_time = 0
        self.hold_cooldown = 0.1

    def process_frame(self, frame):
        """
        Process the input frame to detect hand landmarks
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

                # Move cursor based on index finger position
                if len(landmarks) > 8:
                    index_tip = landmarks[8]
                    screen_w, screen_h = pyautogui.size()
                    cursor_x = np.interp(index_tip[0], [0, w], [0, screen_w])
                    cursor_y = np.interp(index_tip[1], [0, h], [0, screen_h])
                    pyautogui.moveTo(cursor_x, cursor_y, _pause=False)

                # Scroll detection
                self.detect_scroll(landmarks, current_time)

                # Click and hold detection
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
            # Reset states if no hands detected
            if self.is_holding:
                pyautogui.mouseUp()
                self.is_holding = False

            self.stop_scrolling()

        return frame
    
    def detect_scroll(self, landmarks, current_time):
        """
        Detect scroll gesture using index and middle finger landmarks
        """
        if len(landmarks) < 13:
            self.stop_scrolling()
            return
        
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        middle_base = landmarks[9]
        
        # Calculate Manhattan distance (faster than Euclidean)
        distance = abs(index_tip[0] - middle_tip[0]) + abs(index_tip[1] - middle_tip[1])
        
        # Calculate vertical difference for scroll direction
        mid_y = (index_tip[1] + middle_tip[1]) // 2
        vertical_diff = mid_y - middle_base[1]
        direction = 'up' if vertical_diff < -15 else 'down' if vertical_diff > 15 else None

        # Hover scroll zone
        if distance < self.scroll_hover_radius:
            self.landmark_colors[8] = (0, 255, 255)
            self.landmark_colors[12] = (0, 255, 255)
            self.landmark_colors[9] = (0, 255, 255)

            # Active scroll zone
            if distance < self.scroll_radius and direction:
                self.landmark_colors[8] = (255, 0, 255)
                self.landmark_colors[12] = (255, 0, 255)
                self.landmark_colors[9] = (255, 0, 255)
                
                # Start scrolling if not already
                if not self.is_scrolling:
                    self.start_scrolling(direction)
            else:
                # Stop scrolling if in hover but not active
                self.stop_scrolling()
        else:
            # Stop scrolling if distance too far
            self.stop_scrolling()
    
    def start_scrolling(self, direction):
        """Start the scrolling thread"""
        self.is_scrolling = True
        self.scroll_direction = direction
        
        # Start thread if not already running
        with self.scroll_lock:
            if not self.scroll_active:
                self.scroll_active = True
                self.scroll_thread = threading.Thread(target=self._scroll_worker, daemon=True)
                self.scroll_thread.start()
    
    def stop_scrolling(self):
        """Stop scrolling"""
        if self.is_scrolling:
            self.is_scrolling = False
    
    def _scroll_worker(self):
        """Worker thread for smooth scrolling"""
        while self.scroll_active:
            if self.is_scrolling:
                self._perform_scroll()
            time.sleep(self.scroll_interval)
    
    def _perform_scroll(self):
        """Platform-specific scroll implementation"""
        os_name = platform.system()
        if os_name == 'Windows':
            self._windows_scroll()
        elif os_name == 'Linux':
            self._linux_scroll()
        else:
            self._default_scroll()
    
    def _windows_scroll(self):
        """Windows-specific scroll implementation"""
        try:
            import ctypes
            scroll_amount = 120 if self.scroll_direction == 'up' else -120
            ctypes.windll.user32.mouse_event(0x0800, 0, 0, scroll_amount, 0)
        except Exception as e:
            print(f"Windows scroll error: {e}")
            self._default_scroll()
    
    def _linux_scroll(self):
        """Linux-specific scroll implementation"""
        try:
            from Xlib import display
            from Xlib.ext.xtest import fake_input
            from Xlib import X
            
            d = display.Display()
            event_direction = 4 if self.scroll_direction == 'up' else 5
            fake_input(d, X.ButtonPress, event_direction)
            d.sync()
            fake_input(d, X.ButtonRelease, event_direction)
            d.sync()
        except ImportError:
            self._default_scroll()
        except Exception as e:
            print(f"Linux scroll error: {e}")
            self._default_scroll()

    def _default_scroll(self):
        """Fallback scroll implementation"""
        scroll_amount = self.scroll_speed if self.scroll_direction == 'up' else -self.scroll_speed
        pyautogui.scroll(scroll_amount // 3)

    def detect_click_and_hold(self, landmarks, current_time):
        """
        Detect click-and-hold gesture
        """
        if len(landmarks) < 9:
            return

        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        distance = np.linalg.norm(np.array(thumb_tip) - np.array(index_tip))

        # Hover zone for click-and-hold
        if distance < self.hold_hover_radius:
            self.landmark_colors[4] = (0, 255, 255)
            self.landmark_colors[8] = (0, 255, 255)

            # Active zone for click-and-hold
            if distance < self.hold_click_radius:
                self.landmark_colors[4] = (0, 0, 255)
                self.landmark_colors[8] = (0, 0, 255)

                # Start holding if not already
                if not self.is_holding:
                    self.hold_start_time = current_time
                    self.is_holding = True
                    pyautogui.mouseDown()
            else:
                # Release hold if in hover but not active
                if self.is_holding:
                    pyautogui.mouseUp()
                    self.is_holding = False
        else:
            # Release hold if distance too far
            if self.is_holding:
                pyautogui.mouseUp()
                self.is_holding = False

    def detect_thumb_index_contact(self, landmarks, current_time):
        """
        Detect left click gesture
        """
        if (len(landmarks) < 9 or
            current_time - self.last_click_time < self.cooldown or
            self.is_holding):
            return False

        thumb_tip = landmarks[4]
        contact_detected = False

        # Check contact between thumb and index finger
        for idx in [5, 6, 7, 8]:
            distance = np.linalg.norm(np.array(thumb_tip) - np.array(landmarks[idx]))

            # Hover zone
            if distance < self.hover_radius:
                self.landmark_colors[4] = (0, 255, 255)
                self.landmark_colors[idx] = (0, 255, 255)

                # Click zone
                if distance < self.click_radius:
                    self.landmark_colors[4] = (255, 0, 0)
                    self.landmark_colors[idx] = (255, 0, 0)
                    contact_detected = True

        if contact_detected:
            self.last_click_time = current_time
            return True

        return False

    def detect_pinky_wrist_contact(self, landmarks, current_time):
        """
        Detect right click gesture
        """
        if (len(landmarks) < 21 or
            current_time - self.last_right_click_time < self.cooldown):
            return False

        pinky_tip = landmarks[20]
        wrist = landmarks[0]
        distance = np.linalg.norm(np.array(pinky_tip) - np.array(wrist))

        # Hover zone for right click
        if distance < self.right_hover_radius:
            self.landmark_colors[20] = (0, 255, 255)
            self.landmark_colors[0] = (0, 255, 255)

            # Click zone for right click
            if distance < self.right_click_radius:
                self.landmark_colors[20] = (255, 0, 0)
                self.landmark_colors[0] = (255, 0, 0)
                self.last_right_click_time = current_time
                return True

        return False

    def draw_points_only(self, frame, landmarks):
        """
        Draw landmarks on the frame
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
        # Stop scrolling thread
        with self.scroll_lock:
            self.scroll_active = False
            self.is_scrolling = False
            
        # Wait for thread to finish
        if self.scroll_thread and self.scroll_thread.is_alive():
            self.scroll_thread.join(timeout=0.5)
        
        # Release MediaPipe resources
        self.hands.close()