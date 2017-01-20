import asana
from .notification import Notification


class AsanaNotification(Notification):
    def __init__(self, name, workspace_id, project_id, access_token, task_description=None):
        super().__init__(name)
        self.task_id = self.name
        self.workspace_id = workspace_id
        self.project_id = project_id
        self.client = asana.Client.access_token(access_token)
        self._task = None
        self.task_template = {'name': name, 'projects': [self.project_id]}
        if task_description:
            self.task_template['notes'] = task_description

    def _notify(self, msg):
        self.client.tasks.add_comment(self.task['id'], text=msg)
        self.client.tasks.update(self.task['id'], completed=False)

    @property
    def task(self):
        if self._task is None:
            tasks = list(self.client.tasks.find_all(project=self.project_id))
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
