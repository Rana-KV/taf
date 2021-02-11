import enum
import glob
import json
from pathlib import Path
from taf.repository_tool import get_target_path
from taf.utils import run


class LifecycleStage(enum.Enum):
    REPO = (1,)
    HOST = (2,)
    UPDATE = 3

    @classmethod
    def from_name(cls, name):
        stage = {v: k for k, v in LIFECYCLE_NAMES.items()}.get(name)
        if stage is not None:
            return stage
        raise ValueError(f"{name} is not a valid lifecycle stage")

    def to_name(self):
        return LIFECYCLE_NAMES[self]


LIFECYCLE_NAMES = {
    LifecycleStage.REPO: "repo",
    LifecycleStage.HOST: "host",
    LifecycleStage.UPDATE: "update",
}


class Event(enum.Enum):
    SUCCEEDED = 1
    CHANGED = 2
    UNCHANGED = 3
    FAILED = 4
    COMPLETED = 5

    @classmethod
    def from_name(cls, name):
        event = {v: k for k, v in EVENT_NAMES.items()}.get(name)
        if event is not None:
            return event
        raise ValueError(f"{name} is not a valid event")

    def to_name(self):
        return EVENT_NAMES[self]


EVENT_NAMES = {
    Event.SUCCEEDED: "succeeded",
    Event.CHANGED: "changed",
    Event.UNCHANGED: "unchanged",
    Event.FAILED: "failed",
    Event.COMPLETED: "completed",
}


SCRIPTS_DIR = "scripts"
TRANSIENT_KEY = "transient"
PERSISTENT_KEY = "persistent"


def _get_script_path(lifecycle_stage, event):
    return get_target_path(
        f"{SCRIPTS_DIR}/{lifecycle_stage.to_name()}/{event.to_name()}"
    )


def handle_repo_event(
    event,
    auth_repo,
    commits_data,
    error,
    targets_data,
    persistent_data=None,
    transient_data=None,
):
    _handle_event(
        LifecycleStage.REPO,
        event,
        persistent_data,
        transient_data,
        auth_repo,
        commits_data,
        error,
        targets_data,
    )


def _handle_event(
    lifecycle_stage, event, persistent_data, transient_data, *args, **kwargs
):
    prepare_data_name = f"prepare_data_{lifecycle_stage.to_name()}"
    data = globals()[prepare_data_name](
        event, persistent_data, transient_data, *args, **kwargs
    )
    print(data)

    def _execute_handler(handler, lifecycle_stage, event, data):
        script_rel_path = _get_script_path(lifecycle_stage, event)
        result = handler(script_rel_path, data)
        transient_data = result.get(TRANSIENT_KEY)
        persistent_data = result.get(PERSISTENT_KEY)
        # process transient data
        # process persistent data
        data[PERSISTENT_KEY] = persistent_data
        data[TRANSIENT_KEY] = transient_data

    if event in (Event.CHANGED, Event.UNCHANGED, Event.SUCCEEDED):
        _execute_handler(handle_succeeded, lifecycle_stage, Event.SUCCEEDED, data)
        if event == Event.CHANGED:
            _execute_handler(handle_changed, lifecycle_stage, event, data)
        elif event == Event.UNCHANGED:
            _execute_handler(handle_unchanged, lifecycle_stage, event, data)
    elif event == Event.FAILED:
        _execute_handler(handle_failed, lifecycle_stage, event, data)

    # execute completed handler at the end
    _execute_handler(handle_completed, lifecycle_stage, Event.COMPLETED, data)


def handle_succeeded(script_path, data):
    return {}


def handle_changed(script_path, data):
    return {}


def handle_unchanged(script_path, data):
    return {}


def handle_failed(script_path, data):
    return {}


def handle_completed(script_path, data):
    return {}


def execute_scripts(self, auth_repo, scripts_rel_path, data):
    scripts_path = Path(auth_repo.path, scripts_rel_path)
    scripts = glob.glob(f"{scripts_path}/*.py")
    scripts = [script for script in scripts.sort() if script[0].isdigit()]
    for script in scripts:
        # TODO
        json_data = json.dumps(data)
        # each script need to return persistent and transient data and that data needs to be passed into the next script
        # other data should stay the same
        # this function needs to return the transient and persistent data returned by the last script
        output = run("py ", script, "--data ", json_data)

        # transient_data = output.get(TRANSIENT_KEY)
        # persistent_data = output.get(PERSISTENT_KEY)
        # process transient data
        # process persistent data
        # data[PERSISTENT_KEY] = persistent_data
        # data[TRANSIENT_KEY] = transient_data


def prepare_data_repo(
    event,
    transient_data,
    persistent_data,
    auth_repo,
    commits_data,
    error,
    targets_dataa,
):
    # commits should be a dictionary containing new commits,
    # commit before pull and commit after pull
    # commit before pull is not equal to the first new commit
    # if the repository was freshly cloned
    if event in (Event.CHANGED, Event.UNCHANGED, Event.SUCCEEDED):
        event = f"event/{Event.SUCCEEDED.to_name()}"
    else:
        event = f"event/{Event.FAILED.to_name()}"
    import pdb; pdb.set_trace()
    return json.dumps({
        "changed": event == Event.CHANGED,
        "event": event,
        "repo_name": auth_repo.name,
        "error_msg": str(error) if error else "",
        "auth_repo": {
            "data": auth_repo.to_json_dict(),
            "commits": commits_data,
        },
        "target_repos": targets_dataa,
        TRANSIENT_KEY: transient_data,
        PERSISTENT_KEY: persistent_data,
    }, indent=4)


# {
#     dependecies: {
#         # about the repository from dependencies.json - in repo data
#     },
#     changed: true/false,
#     error_msg: text,
#     event: event type (update/succeeded),
#     repo_name: cityofsanmateo/law,
#     auth_repo: {
#         "data":{
#             name: cityofsanmateo/law
#             path: path on disk
#             custom: {
#                 custom data from dependencies.json
#             },
#             urls: repo urls
#             hosts: hosts
#         }
#         new_commits: [],
#         commits_before_pull: []
#         commits_after_pull: []
#     },
#     target_repos:{
#         cityofsanamteo/law-xml: {
#             data: {
#                 name: cityofsanamteo/law-xml,
#                 path: path on disk,
#                 custom: {
#                     custom data from repositories.json
#                 },
#                 ursl: repo urls
#             },
#             branch1:{
#                 commit_before_pull: {"commit": commit0, "custom": {...}}
#                 new_commits: [{"commit": commit1, "custom": {...}}, {"commit": commit2, "custom": {...}}, {"commit": commit3, "custom": {}}]
#                 commit_after_pull: {"commit": commit3, "custom": {}}
#             }
#             branch2: [{"commit": commit4, "custom: {...}}, {"commit": commit5, "custom": {}}]
#         }
#     },
#     transient_state: {
#         //if one script failed - return that error (updated after every script in every handler, but not saved to disk)
#     },
#     persistent_state: { // persisted after every script in every handler (same file every time in library root) - save to a temp file and move it
#         cityofsanmateo/law-xml: {
#             update/succeeded: {
#                 ...
#             }
#         }
#     },
# }

def prepare_data_host():
    return {}


def prepare_data_completed():
    return {}
