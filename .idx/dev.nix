

# To learn more about how to use Nix to configure your environment
# see: https://developers.google.com/idx/guides/customize-idx-env
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-23.11"; # or "unstable"
  # Use https://search.nixos.org/packages to find packages
  packages = [ 
    pkgs.python312 
    pkgs.poetry 
    pkgs.poetryPlugins.poetry-plugin-export 
    pkgs.gcc 
  ];
  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [ "ms-python.python" ];
    workspace = {
      # Runs when a workspace is first created with this `dev.nix` file
      onCreate = {
        install =
          "python3.12 -m venv .venv         && source .venv/bin/activate         && pip install -r requirements.txt";
      };
      # To run something each time the environment is rebuilt, use the `onStart` hook
    };
    # Enable previews and customize configuration
    previews = {
      enable = true;
      previews = [{
        command = [ "./start.sh" ];
        id = "web";
        manager = "web";
      }];
    };
  };
}
