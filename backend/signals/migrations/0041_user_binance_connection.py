from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0040_paper_trade_fear_greed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserBinanceConnection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_key_enc', models.BinaryField()),
                ('api_secret_enc', models.BinaryField()),
                ('api_key_hint', models.CharField(blank=True, max_length=12)),
                ('status', models.CharField(
                    choices=[
                        ('ACTIVE', 'Active'),
                        ('PAUSED', 'Paused'),
                        ('REVOKED', 'Revoked'),
                        ('BROKEN', 'Broken'),
                    ],
                    default='PAUSED', max_length=10,
                )),
                ('permissions', models.JSONField(blank=True, default=dict)),
                ('ip_check_passed', models.BooleanField(default=False)),
                ('last_check_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=models.deletion.CASCADE,
                    related_name='binance_connection',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'User Binance Connection',
                'verbose_name_plural': 'User Binance Connections',
                'db_table': 'user_binance_connection',
            },
        ),
    ]
