from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("habits", "0005_checkin_used_freeze_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerprofile",
            name="weekly_boss_claims",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
