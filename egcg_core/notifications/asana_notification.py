import asana
from .notification import Notification


class AsanaNotification(Notification):
    config_domain = 'asana'

    def __init__(self, task_id):
        super().__init__(task_id)
        self.task_id = self.name
        self.client = asana.Client.access_token(self.config['access_token'])
        self.workspace_id = self.config['workspace_id']
        self.project_id = self.config['project_id']
        self._task = None
        self.task_template = {
            'name': task_id,
            'notes': self.config.get('task_description'),
            'projects': [self.project_id]
        }

    def notify(self, msg):
        self.client.tasks.add_comment(self.task['id'], text=msg)
        self.client.tasks.update(self.task['id'], completed=False)

    @property
    def task(self):
        if self._task is None:
            tasks = list(self.client.tasks.find_all(project=self.project_id, completed=False))
            task_ent = self._get_entity(tasks, self.task_id)
            if task_ent is None:
                task_ent = self._create_task()
            self._task = self.client.tasks.find_by_id(task_ent['id'])
        return self._task

    @staticmethod
    def _get_entity(collection, name):
        for e in collection:
            if e['name'] == name:
                return e

    def _create_task(self):
        return self.client.tasks.create_in_workspace(self.workspace_id, self.task_template)
