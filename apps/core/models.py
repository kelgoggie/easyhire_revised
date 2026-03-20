from django.db import models


class Province(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)

    class Meta:
        db_table = "provinces"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CityMunicipality(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, related_name="cities"
    )

    class Meta:
        db_table = "cities_municipalities"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Barangay(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    city = models.ForeignKey(
        CityMunicipality, on_delete=models.CASCADE, related_name="barangays"
    )

    class Meta:
        db_table = "barangays"
        ordering = ["name"]

    def __str__(self):
        return self.name