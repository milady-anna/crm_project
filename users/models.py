from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Расширяем стандартного пользователя Django.
    Добавляем только то, чего ему не хватает.
    """
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Номер телефона"
    )
    
    # Указываем, как красиво отображать пользователя в админке
    def __str__(self):
        return self.get_full_name() or self.username