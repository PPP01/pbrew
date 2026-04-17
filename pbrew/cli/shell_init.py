import click
from pbrew.core.paths import bin_dir


_BASH_INIT = '''\
# pbrew shell integration — automatisch generiert von "pbrew shell-init bash"
export PBREW_ROOT="{prefix}"
export PATH="{bin_dir}:$PATH"

# pbrew use/switch/unswitch: aktualisiert PBREW_PATH und PBREW_ACTIVE
pbrew() {{
    if [ "$1" = "use" ] || [ "$1" = "switch" ] || [ "$1" = "unswitch" ]; then
        local _pbrew_out
        _pbrew_out="$(command pbrew "$@")"
        local _pbrew_rc=$?
        [ $_pbrew_rc -eq 0 ] && eval "$_pbrew_out"
        return $_pbrew_rc
    else
        command pbrew "$@"
    fi
}}

[ -f "$PBREW_ROOT/.switch" ] && source "$PBREW_ROOT/.switch"
'''

_ZSH_INIT = '''\
# pbrew shell integration — automatisch generiert von "pbrew shell-init zsh"
export PBREW_ROOT="{prefix}"
export PATH="{bin_dir}:$PATH"

pbrew() {{
    if [[ "$1" == "use" || "$1" == "switch" || "$1" == "unswitch" ]]; then
        local _pbrew_out
        _pbrew_out="$(command pbrew "$@")"
        local _pbrew_rc=$?
        [ $_pbrew_rc -eq 0 ] && eval "$_pbrew_out"
        return $_pbrew_rc
    else
        command pbrew "$@"
    fi
}}

[ -f "$PBREW_ROOT/.switch" ] && source "$PBREW_ROOT/.switch"
'''


_FISH_INIT = '''\
# pbrew shell integration — automatisch generiert von "pbrew shell-init fish"
set -x PBREW_ROOT "{prefix}"
fish_add_path "{bin_dir}"

function pbrew
    if test "$argv[1]" = "use" -o "$argv[1]" = "switch" -o "$argv[1]" = "unswitch"
        set _pbrew_out (command pbrew $argv)
        set _pbrew_rc $status
        if test $_pbrew_rc -eq 0
            eval $_pbrew_out
        end
        return $_pbrew_rc
    else
        command pbrew $argv
    end
end

test -f "$PBREW_ROOT/.switch.fish" && source "$PBREW_ROOT/.switch.fish"
'''


@click.command("shell-init")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
@click.pass_context
def shell_init_cmd(ctx, shell):
    """Gibt Shell-Integration aus (in ~/.bashrc oder ~/.zshrc einbinden)."""
    prefix = ctx.obj["prefix"]
    templates = {"bash": _BASH_INIT, "zsh": _ZSH_INIT, "fish": _FISH_INIT}
    template = templates[shell]
    click.echo(template.format(
        prefix=prefix,
        bin_dir=bin_dir(prefix),
    ))
