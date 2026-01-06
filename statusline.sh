#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract Claude Code context
current_dir=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
model_name=$(echo "$input" | jq -r '.model.display_name')
output_style=$(echo "$input" | jq -r '.output_style.name // "default"')

# Shorten the path for display (matching your bash function)
shorten_path() {
    local fullpath="$1"
    local home_tilde="$HOME"
    local prefix_length=3 # Number of leading components to keep
    local suffix_length=2 # Number of trailing components to keep
    local parts shortened_path

    # Replace home directory with ~
    if [[ "$fullpath" == "$home_tilde"* ]]; then
        fullpath="~${fullpath#$home_tilde}"
    fi

    # Split the path into components
    IFS="/" read -r -a parts <<<"$fullpath"

    # Check if shortening is necessary
    if ((${#parts[@]} > prefix_length + suffix_length + 1)); then
        shortened_path=$(printf "/%s" "${parts[@]:0:prefix_length}")
        shortened_path+="/..."
        shortened_path+=$(printf "/%s" "${parts[@]: -suffix_length}")
        shortened_path="${shortened_path#/}" # Remove leading slash
    else
        shortened_path="$fullpath"
    fi

    echo "$shortened_path"
}

# Set virtualenv indicator
set_virtualenv() {
    if [ -z "$VIRTUAL_ENV" ]; then
        PYTHON_VIRTUALENV=""
    else
        PYTHON_VIRTUALENV="(venv: $(basename "$VIRTUAL_ENV")) "
    fi
}

# Set git branch indicator
set_git_branch() {
    cd "$current_dir" 2>/dev/null || return
    
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        BRANCH=""
        return
    fi

    local branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    if [[ $branch == "HEAD" ]]; then
        branch="DETACHED:$(git describe --tags --always 2>/dev/null)"
    fi

    local git_status="$(git status --porcelain=v1 --branch 2>/dev/null)"
    local changes=""
    local remote_state=""

    # Count changes (staged + unstaged)
    local change_count="$(echo "$git_status" | grep -Evc '^#' | xargs)"
    [ "$change_count" -ne 0 ] && changes=" | $change_count"

    # Detect remote status
    if [[ $git_status =~ "ahead ([0-9]+)" ]]; then
        remote_state=" ↑"
    elif [[ $git_status =~ "behind ([0-9]+)" ]]; then
        remote_state=" ↓"  
    elif [[ $git_status =~ "diverged" ]]; then
        remote_state=" ↕"
    fi

    # Format branch info (colors will be dimmed by Claude Code)
    if [ "$change_count" -ne 0 ]; then
        BRANCH="[${branch}${changes}]${remote_state}" # Changes present
    else
        BRANCH="[${branch}${changes}]${remote_state}" # Clean
    fi
}

# Main execution
set_virtualenv
set_git_branch
shortened_path=$(shorten_path "$current_dir")

# Build the status line (matching your PS1 format but adapted for Claude Code)
status_line="${PYTHON_VIRTUALENV}[${shortened_path}]"
[ -n "$BRANCH" ] && status_line="${status_line} ${BRANCH}"
status_line="${status_line} | ${model_name}"
[ "$output_style" != "default" ] && status_line="${status_line} (${output_style})"

printf "%s" "$status_line"