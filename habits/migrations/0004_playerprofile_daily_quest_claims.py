from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("habits", "0003_playerprofile_achievements_unlocked"),
    ]

    operations = [
        migrations.AddField(
            model_name="playerprofile",
            name="daily_quest_claims",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
