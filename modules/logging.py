import logging
import sys

class ColorFormatter(logging.Formatter):

    COLORS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[1;41m",  # bold + red background
    }
    RESET = "\033[0m"
    GRAY = "\033[90m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname:<8}{self.RESET}"
        record.name = f"{self.GRAY}{record.name:<20}{self.RESET}"
        record.msg = f"{color}{record.msg}{self.RESET}"
        
        return super().format(record)


def setup_logging(level=logging.INFO):
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%d.%m.%y %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorFormatter(fmt, datefmt=datefmt))

    logging.basicConfig(level=level, handlers=[handler])

    logging.getLogger("aiogram.event").setLevel(logging.WARNING)