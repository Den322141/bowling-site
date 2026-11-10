import os
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
MAX_IMAGE_SIZE_MB = 5


def validate_image_file(file):
    if not file:
        return

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Неподдерживаемый формат файла: '{ext}'. Разрешены только: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}."
        )

    file_size = getattr(file, 'size', 0)
    if file_size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(
            f"Размер файла ({file_size / (1024 * 1024):.1f} МБ) превышает максимально допустимый ({MAX_IMAGE_SIZE_MB} МБ)."
        )
