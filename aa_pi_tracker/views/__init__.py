from .buildout import buildout_page
from .characters import (
    add_character,
    characters_page,
    remove_character,
    trigger_price_sync,
    trigger_sync,
)
from .corp_projects import (
    corp_project_add_objective,
    corp_project_delete_objective,
    corp_project_set_participants,
    corp_projects_member_page,
    corp_projects_page,
    create_corp_project,
    delete_corp_project,
    toggle_share_character,
)
from .extractors import extractors_page
from .maintenance import maintenance_char_page, maintenance_page, maintenance_save_state
from .optimizer import (
    optimizer_analyze_json,
    optimizer_create_corp_project,
    optimizer_create_project,
    optimizer_page,
    save_home_system,
)
from .overview import index
from .planets import (
    planet_optimizer_json,
    planets_page,
    set_planet_resource,
    system_search,
)
from .profit import profit_page
from .projects import (
    add_objective,
    add_project_planet,
    create_project,
    delete_objective,
    delete_project,
    edit_objective,
    project_analysis_json,
    projects_page,
    remove_project_planet,
    update_project_planet_role,
)

__all__ = [
    "index",
    "add_character", "remove_character", "trigger_sync", "trigger_price_sync", "characters_page",
    "extractors_page",
    "planets_page", "system_search", "planet_optimizer_json", "set_planet_resource",
    "projects_page", "create_project", "delete_project",
    "add_objective", "edit_objective", "delete_objective",
    "add_project_planet", "remove_project_planet", "project_analysis_json",
    "update_project_planet_role",
    "profit_page",
    "optimizer_page", "optimizer_analyze_json",
    "optimizer_create_project", "optimizer_create_corp_project",
    "save_home_system",
    "buildout_page",
    "maintenance_page", "maintenance_char_page", "maintenance_save_state",
    "corp_projects_page", "corp_projects_member_page",
    "create_corp_project", "delete_corp_project",
    "corp_project_set_participants", "corp_project_add_objective", "corp_project_delete_objective",
    "toggle_share_character",
]
