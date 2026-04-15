import click
from pbrew.core.paths import get_prefix, bin_dir


_BASH_INIT = '''\
# pbrew shell integration — automatisch generiert von "pbrew shell-init bash"
export PBREW_ROOT="{prefix}"
export PATH="{bin_dir}:$PATH"

# pbrew use: setzt PBREW_PHP in der aktuellen Shell
pbrew() {{
    local cmd="$1"
    if [ "$cmd" = "use" ] || [ "$cmd" = "switch" ]; then
        eval "$(command pbrew "$@")"
    else
        command pbrew "$@"
    fi
}}
'''

_ZSH_INIT = '''\
# pbrew shell integration — automatisch generiert von "pbrew shell-init zsh"
export PBREW_ROOT="{prefix}"
export PATH="{bin_dir}:$PATH"

pbrew() {{
    local cmd="$1"
    if [[ "$cmd" == "use" || "$cmd" == "switch" ]]; then
        eval "$(command pbrew "$@")"
    else
        command pbrew "$@"
    fi
}}
'''


@click.command("shell-init")
@click.argument("shell", type=click.Choice(["bash", "zsh"]))
@click.pass_context
def shell_init_cmd(ctx, shell):
    """Gibt Shell-Integration aus (in ~/.bashrc oder ~/.zshrc einbinden)."""
    prefix = ctx.obj["prefix"]
    template = _BASH_INIT if shell == "bash" else _ZSH_INIT
    click.echo(template.format(
        prefix=prefix,
        bin_dir=bin_dir(prefix),
    ))
