import yaml


def load_config(raw: str):
    return yaml.safe_load(raw)


if __name__ == "__main__":
    print(load_config("enabled: true"))

