# Changelog

## 0.1.0 (2026-03-29)


### Bug Fixes

* address PR review feedback - test unpacking, auth convention, settings, docs ([82695f2](https://github.com/JoelMdO/Content-Manager-Editor-Backend/commit/82695f2d396e7902dbbc36acbedd6fa09d08621c))
* guard debug_toolbar URL inclusion with DEBUG check to fix integration container startup ([171f023](https://github.com/JoelMdO/Content-Manager-Editor-Backend/commit/171f023db5946e3b5fcf94dc0b23501891573c60))
* pin PROXY_KEY in UpsertUserViewTests setUp/tearDown to fix CI failures ([eafc0db](https://github.com/JoelMdO/Content-Manager-Editor-Backend/commit/eafc0dbc10231a433528265993a9c65874af7623))
* regenerate uv.lock and fix all ruff lint errors ([bbfa7b7](https://github.com/JoelMdO/Content-Manager-Editor-Backend/commit/bbfa7b761c4f1c425dd20b58460b38688624c0be))
* use LocMemCache fallback when REDIS_URL is empty to fix integration test 500s ([637fc3d](https://github.com/JoelMdO/Content-Manager-Editor-Backend/commit/637fc3d749873bbff53220265f157c7d898ddcd5))

## Changelog

Initially all project updates were added here but since this project is always
getting updates it never really gets released like a library would so moving
forward there won't be version tags or a changelog.

Originally I cut release tags at an arbitrary point in time but the expectation
was to always use the latest main commit. If you look at the history of this
file you'll see it's been over a year since the last tagged release but there's
been tons of new commits. This project is very active and changing, it's just
not versioned.

You can view the [list of
commits](https://github.com/nickjj/docker-django-example/commits) for changes
moving forward!
