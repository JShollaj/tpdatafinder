import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import pytesseract
from django.conf import settings

DEFAULT_CHECK_COMMAND = "which"
WINDOWS_CHECK_COMMAND = "where"
TESSERACT_DATA_PATH_VAR = 'TESSDATA_PREFIX'

VALID_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".gif", ".png", ".tga", ".tif", ".bmp"]

def create_directory(path):

    if not os.path.exists(path):
        os.makedirs(path)


def check_path(path):
    return bool(os.path.exists(path))


def get_command():
    if sys.platform.startswith('win'):
        return WINDOWS_CHECK_COMMAND
    return DEFAULT_CHECK_COMMAND



def check_pre_requisites_tesseract():
    check_command = get_command()
    logging.debug("Running `{}` to check if tesseract is installed or not.".format(check_command))

    result = subprocess.run([check_command, 'tesseract'], stdout=subprocess.PIPE)
    if not result.stdout:
        logging.error("tesseract-ocr missing, install `tesseract` to resolve. Refer to README for more instructions.")
        return False
    logging.debug("Tesseract correctly installed!\n")

    if sys.platform.startswith('win'):
        environment_variables = os.environ
        logging.debug(
            "Checking if the Tesseract Data path is set correctly or not.\n")
        if TESSERACT_DATA_PATH_VAR in environment_variables:
            if environment_variables[TESSERACT_DATA_PATH_VAR]:
                path = environment_variables[TESSERACT_DATA_PATH_VAR]
                logging.debug("Checking if the path configured for Tesseract Data Environment variable `{}` \
                as `{}` is valid or not.".format(TESSERACT_DATA_PATH_VAR, path))
                if os.path.isdir(path) and os.access(path, os.R_OK):
                    logging.debug("All set to go!")
                    return True
                else:
                    logging.error(
                        "Configured path for Tesseract data is not accessible!")
                    return False
            else:
                logging.error("Tesseract Data path Environment variable '{}' configured to an empty string!\
                ".format(TESSERACT_DATA_PATH_VAR))
                return False
        else:
            logging.error("Tesseract Data path Environment variable '{}' needs to be configured to point to\
            the tessdata!".format(TESSERACT_DATA_PATH_VAR))
            return False
    else:
        return True


def main(input_path):
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
    if not check_pre_requisites_tesseract():
        return

    if not check_path(input_path):
        logging.error("Nothing found at `{}`".format(input_path))
        return

    text = pytesseract.image_to_string(input_path)

    return text
