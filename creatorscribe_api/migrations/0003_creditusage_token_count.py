from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('creatorscribe_api', '0002_alter_client_client_name_alter_client_contact_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='creditusage',
            name='token_count',
            field=models.PositiveIntegerField(default=1, help_text='Number of tokens consumed by this action'),
        ),
    ]
