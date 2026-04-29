#!/usr/bin/env bash
set -euo pipefail

session_dir="${1:?session dir is required}"
from_version="${2:?from version is required}"
to_version="${3:?to version is required}"
source_dir="${4:?source dir is required}"

current_dir="${session_dir}/current"
backup_dir="${session_dir}/current_backup"
action_log="${session_dir}/logs/hot-update-script.log"

mkdir -p "${session_dir}/logs"

if [[ ! -d "${source_dir}" ]]; then
  echo "target source directory does not exist: ${source_dir}" >&2
  exit 1
fi

rm -rf "${backup_dir}"
if [[ -d "${current_dir}" ]]; then
  cp -R "${current_dir}" "${backup_dir}"
fi

rm -rf "${current_dir}"
cp -R "${source_dir}" "${current_dir}"

printf '[%s] from=%s to=%s source=%s\n' \
  "$(date -Iseconds)" \
  "${from_version}" \
  "${to_version}" \
  "${source_dir}" >> "${action_log}"

echo "replaced ${current_dir} with ${source_dir}"
