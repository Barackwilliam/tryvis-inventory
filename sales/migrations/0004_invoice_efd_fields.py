from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("sales", "0003_payment")]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="efd_receipt_number",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="invoice",
            name="efd_qr_image",
            field=models.TextField(blank=True, default=""),
        ),
    ]
