"""Django management command to clean up orphaned periodic tasks."""
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask


class Command(BaseCommand):
    help = 'Clean up orphaned periodic tasks (forex, nepse, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        orphan_patterns = [
            'forex',
            'nepse',
            'scan_forex',
            'scan_nepse',
        ]

        self.stdout.write('Checking for orphaned periodic tasks...\n')

        tasks_to_delete = []
        for task in PeriodicTask.objects.all():
            task_name_lower = task.name.lower()
            task_task_lower = task.task.lower() if task.task else ''

            for pattern in orphan_patterns:
                if pattern in task_name_lower or pattern in task_task_lower:
                    tasks_to_delete.append(task)
                    break

        if not tasks_to_delete:
            self.stdout.write(self.style.SUCCESS('No orphaned tasks found.'))
            return

        self.stdout.write(f'Found {len(tasks_to_delete)} orphaned task(s):\n')
        for task in tasks_to_delete:
            self.stdout.write(f'  - {task.name} ({task.task})')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\nDry run - no tasks deleted.'))
        else:
            for task in tasks_to_delete:
                task.delete()
                self.stdout.write(self.style.SUCCESS(f'  Deleted: {task.name}'))

            self.stdout.write(self.style.SUCCESS(f'\nDeleted {len(tasks_to_delete)} orphaned task(s).'))
