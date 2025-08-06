"""OSS (Object Storage Service) module for newsletter system"""

from .wrapper import OSSUploaderWrapper as OSSUploader

__all__ = ['OSSUploader']