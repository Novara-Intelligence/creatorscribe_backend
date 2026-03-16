from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('creatorscribe_api', '0007_socialaccount'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Drop old index referencing 'user' before renaming the field
        migrations.RemoveIndex(
            model_name='client',
            name='clients_user_id_fe4fee_idx',
        ),
        # Rename user -> owner
        migrations.RenameField(
            model_name='client',
            old_name='user',
            new_name='owner',
        ),
        # Add new index referencing 'owner'
        migrations.AddIndex(
            model_name='client',
            index=models.Index(fields=['owner', 'client_name'], name='clients_owner_client_name_idx'),
        ),
        # Create ClientMember model
        migrations.CreateModel(
            name='ClientMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('admin', 'Admin'), ('editor', 'Editor'), ('viewer', 'Viewer')],
                    default='viewer',
                    help_text='Permission level for this member',
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('accepted', 'Accepted')],
                    default='pending',
                    help_text='Whether the invite has been accepted',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(
                    help_text='Client this membership belongs to',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='creatorscribe_api.client',
                )),
                ('invited_by', models.ForeignKey(
                    help_text='User who sent the invite',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_invites',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    help_text='Invited user',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='client_memberships',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Client Member',
                'verbose_name_plural': 'Client Members',
                'db_table': 'client_members',
            },
        ),
        migrations.AlterUniqueTogether(
            name='clientmember',
            unique_together={('client', 'user')},
        ),
        migrations.AddIndex(
            model_name='clientmember',
            index=models.Index(fields=['client', 'status'], name='client_members_client_status_idx'),
        ),
        migrations.AddIndex(
            model_name='clientmember',
            index=models.Index(fields=['user', 'status'], name='client_members_user_status_idx'),
        ),
    ]
