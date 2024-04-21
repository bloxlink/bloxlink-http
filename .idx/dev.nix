# To learn more about how to use Nix to configure your environment
# see: https://developers.google.com/idx/guides/customize-idx-env
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-23.11"; # or "unstable"
  # Use https://search.nixos.org/packages to find packages
  packages = [
    pkgs.python312
    pkgs.gcc
    pkgs.openssh
    pkgs.poetry
  ];
  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      "ms-python.python"
      # "ms-python.pylint"
      "ms-python.pylance"
      "humao.rest-client"
      "WakaTime.vscode-wakatime"
    ];
    workspace = {
      # Runs when a workspace is first created with this `dev.nix` file
      onCreate = {
        install =
          "python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt";
      };
      onStart = {
        start-proxy = "ssh -R local.blox.link:80:localhost:8010 localhost.run";
        update = "poetry update; poetry export --without-hashes --format=requirements.txt > requirements.txt; python3.12 -m venv .venv && source .venv/bin/activate && pip install -U -r requirements.txt";
        run = "echo 'starting bot in 20 seconds'; sleep 20; source .venv/bin/activate; python3.12 src/bot.py";
      };
    };
  #   previews = {
  #   enable = true;
  #   previews = [
  #     {
  #       command = [
  #         # "source"
  #         # ".venv/bin/activate;"
  #         # "./start.sh"
  #         # "bot.py"
  #         # "--port"
  #         # "$PORT"
  #         # "--host"
  #         # "0.0.0.0"
  #         # "--disable-host-check"
  #       ];
  #       cwd = "src";
  #       manager = "web";
  #       id = "web";
  #     }
  #   ];
  # };
  };
}
