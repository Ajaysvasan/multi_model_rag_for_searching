# OCR processing module
# Uses Tesseract OCR for completely offline text extraction
# Automatically downloads and installs Tesseract if not found on the user's device ---> New change

import os
import sys
import shutil
import platform
import subprocess
import tempfile
import urllib.request
import cv2
import numpy as np
from PIL import Image
import pytesseract

# Tesseract auto-downloader class for users if they don't have tesseract in their system

class TesseractInstaller:

    # Latest Windows installer hosted by UB Mannheim (official source)
    WINDOWS_INSTALLER_URL = (
        "https://digi.bib.uni-mannheim.de/tesseract/"
        "tesseract-ocr-w64-setup-5.5.0.20241111.exe"
    )
    WINDOWS_INSTALL_DIR = r"C:\Program Files\Tesseract-OCR"

    def install(self):
        
        # This is the entry point which is called by OCR process if tesseract not available in the user's system
        # Picks the right installer for the current OS and install tesseract for that OS of the user or 
        
        system = platform.system()

        if system == "Windows":
            success = self._install_windows()
        elif system == "Linux":
            success = self._install_linux()
        elif system == "Darwin":
            success = self._install_macos()
        else:
            print(f"Unsupported OS: {system}")
            return False

        # Final check — is tesseract callable
        if success and shutil.which("tesseract"):
            print("Tesseract installed successfully.")
            return True

        print("Installation finished but tesseract is still not found in PATH.")
        return False

    # Installation for Windows OS
    
    def _install_windows(self) -> bool:
        print("Downloading Tesseract installer for Windows ...")

        installer_path = os.path.join(tempfile.gettempdir(), "tesseract-setup.exe")

        try:
            urllib.request.urlretrieve(self.WINDOWS_INSTALLER_URL, installer_path)
        except Exception as e:
            print(f"Download failed: {e}")
            return False

        print("Running installer silently — this may take a moment ...")

        try:
            # /S = silent install; installs to default dir and updates PATH
            subprocess.run([installer_path, "/S"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Installer exited with error: {e}")
            return False
        except Exception as e:
            print(f"Failed to run installer: {e}")
            return False
        finally:
            # Clean up the downloaded exe regardless of outcome
            if os.path.exists(installer_path):
                os.remove(installer_path)

        # The silent installer updates the system PATH in the registry,
        # but the *current* process still has the old PATH in memory.
        # Refresh it so pytesseract can find tesseract without a restart.
        self._refresh_windows_path()

        return True

    @staticmethod
    def _refresh_windows_path():
        # For refreshing the OS and updating the tesseract path.
        try:
            import winreg

            # System-wide PATH
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            )
            sys_path, _ = winreg.QueryValueEx(key, "Path")
            winreg.CloseKey(key)

            # Per-user PATH
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
            try:
                user_path, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                user_path = ""
            winreg.CloseKey(key)

            os.environ["PATH"] = sys_path + os.pathsep + user_path
        except Exception as e:
            # Non-fatal — worst case the user restarts the terminal
            print(f"Could not refresh PATH from registry: {e}")
            print(f"If tesseract is not found, restart your terminal.")

    # Installer for Linux OS
    def _install_linux(self) -> bool:
        distro = self._detect_linux_distro()
        print(f"Detected Linux distribution: {distro}")

        # Map each known distro family to its install command
        commands = {
            "debian": ["sudo", "apt-get", "update"],
            "fedora": None,
            "arch":   None,
        }

        if distro == "debian":
            print("Installing tesseract via apt ...")
            try:
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "tesseract-ocr"],
                    check=True,
                )
                return True
            except subprocess.CalledProcessError as e:
                print(f"apt install failed: {e}")
                return False

        elif distro == "fedora":
            print("Installing tesseract via dnf ...")
            try:
                subprocess.run(
                    ["sudo", "dnf", "install", "-y", "tesseract"],
                    check=True,
                )
                return True
            except subprocess.CalledProcessError as e:
                print(f"dnf install failed: {e}")
                return False

        elif distro == "arch":
            print("Installing tesseract via pacman ...")
            try:
                subprocess.run(
                    ["sudo", "pacman", "-S", "-y", "tesseract", "tesseract-data-eng"],
                    check=True,
                )
                return True
            except subprocess.CalledProcessError as e:
                print(f"pacman install failed: {e}")
                return False

        else:
            # Unknown distro — try apt as a best-effort fallback
            print(f"Unknown distro '{distro}'. Trying apt as fallback ...")
            try:
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(
                    ["sudo", "apt-get", "install", "-y", "tesseract-ocr"],
                    check=True,
                )
                return True
            except Exception as e:
                print(f"Fallback install failed: {e}")
                print("Please install tesseract manually: sudo apt-get install tesseract-ocr")
                return False

    @staticmethod
    def _detect_linux_distro() -> str:
        # If the OS is unknown linux system then this check for distro
        try:
            with open("/etc/os-release") as f:
                content = f.read().lower()

            if "ubuntu" in content or "debian" in content or "linuxmint" in content:
                return "debian"
            if "fedora" in content or "rhel" in content or "centos" in content or "rocky" in content:
                return "fedora"
            if "arch" in content or "manjaro" in content:
                return "arch"

            # Extract the raw ID= value as a last resort
            for line in content.splitlines():
                if line.startswith("id="):
                    return line.split("=")[1].strip('"')

        except FileNotFoundError:
            pass

        return "unknown"

    # Installer for macOS
    def _install_macos(self) -> bool:
        # Homebrew is required; install it first if missing
        if not shutil.which("brew"):
            print("Homebrew not found. Installing Homebrew first ...")
            try:
                subprocess.run(
                    [
                        "/bin/bash", "-c",
                        'curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash',
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                print(f"Homebrew installation failed: {e}")
                return False

        print("Installing tesseract via Homebrew ...")
        try:
            subprocess.run(["brew", "install", "tesseract"], check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Homebrew install failed: {e}")
            return False


# Main OCR Processor
class OCRProcessor:
    def __init__(self, lang='eng'):

        self.lang = lang
        self._ensure_tesseract()

    def _ensure_tesseract(self):
        # Check whether the user's system contains tesseract
        if shutil.which("tesseract"):
            # Already installed — just print the version and move on
            version = pytesseract.get_tesseract_version()
            print(f"Tesseract OCR v{version} found - Running in OFFLINE mode")
            return

        # Not found — attempt automatic installation
        print("Tesseract OCR not found. Attempting automatic installation ...")
        installer = TesseractInstaller()
        success = installer.install()

        if not success:
            raise RuntimeError(
                "Automatic Tesseract installation failed.\n"
                "Please install it manually:\n"
                "  Windows : https://github.com/UB-Mannheim/tesseract/wiki\n"
                "  Linux   : sudo apt-get install tesseract-ocr\n"
                "  macOS   : brew install tesseract\n"
            )

        # Confirm it is actually callable after install
        version = pytesseract.get_tesseract_version()
        print(f"Tesseract OCR v{version} found - Running in OFFLINE mode")

    def has_text(self, image: Image.Image, threshold=0.01) -> bool:
        # Checks whether the given image contains text or not.
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.sum(edges > 0) / edges.size

        return edge_density > threshold

    def extract_text(self, image: Image.Image, config='--psm 3'):
       # Extraction of text from the image
        try:
            image_np = np.array(image)

            # Normalise to 3-channel RGB so Tesseract is happy
            if len(image_np.shape) == 2:                # grayscale
                image_np = cv2.cvtColor(image_np, cv2.COLOR_GRAY2RGB)
            elif image_np.shape[2] == 4:                # RGBA
                image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)

            # Detailed per-word data (includes confidence per word)
            ocr_data = pytesseract.image_to_data(
                image_np,
                lang=self.lang,
                config=config,
                output_type=pytesseract.Output.DICT,
            )

            # Full-page text string
            full_text = pytesseract.image_to_string(
                image_np,
                lang=self.lang,
                config=config,
            )

            # Average confidence — Tesseract uses -1 for non-word rows; filter those out
            confidences = [
                float(c) for c in ocr_data['conf']
                if c != -1 and c != '-1'
            ]
            avg_confidence = np.mean(confidences) if confidences else 0.0

            # Per-word details with bounding boxes
            word_details = []
            for i in range(len(ocr_data['text'])):
                if int(ocr_data['conf'][i]) > 0:
                    word_details.append({
                        'text':       ocr_data['text'][i],
                        'confidence': float(ocr_data['conf'][i]),
                        'bbox': (
                            ocr_data['left'][i],
                            ocr_data['top'][i],
                            ocr_data['width'][i],
                            ocr_data['height'][i],
                        ),
                    })

            return {
                "text":         full_text.strip(),
                "confidence":   avg_confidence / 100.0,   # scale to 0–1
                "word_details": word_details,
            }

        except Exception as e:
            print(f"OCR Error: {e}")
            return {
                "text":         "",
                "confidence":   0.0,
                "word_details": [],
            }

    def extract_text_enhanced(self, image: Image.Image):
        
        img_np = np.array(image)

        # Convert to single-channel grayscale
        if len(img_np.shape) == 3:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_np

        # Otsu binarisation — automatically picks the best threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Median filter to remove salt-and-pepper noise
        denoised = cv2.medianBlur(binary, 3)

        preprocessed = Image.fromarray(denoised)
        return self.extract_text(preprocessed)


# if __name__ == "__main__":

#     file_directory = input("Enter a valid images file directory: ")

#     # Initialize processors
#     images = ImagePreprocessor()
#     ocr_processor = OCRProcessor(lang='eng')  # Use 'eng' for English

#     # Process images
#     preprocessed_images = images.process_directory(file_directory)

#     for img, filename in preprocessed_images:

#         if not ocr_processor.has_text(img): # Checks every image whether they contain text or not
#             # If no text it skip that image and proceed with next image
#             # else it will start to extract the text from the image....

#             print("No text in image \n Proceeds with next image")
#             continue

#         # Extract text
#         ocr_result = ocr_processor.extract_text(img)

#         print(f" Confidence: {ocr_result['confidence']:.2%}")
#         print(f" Words detected: {len(ocr_result['word_details'])}")

#         if ocr_result['text']:
#             print("\n Extracted Text:")
#             print(ocr_result["text"])
#             print()

#             # Show top 5 words with confidence
#             if ocr_result['word_details']:
#                 print("\n Sample word confidences:")
#                 for word_info in ocr_result['word_details'][:5]:
#                     print(f"   '{word_info['text']}' - {word_info['confidence']:.1f}%")
#         else:
#             print("No text extracted from image")