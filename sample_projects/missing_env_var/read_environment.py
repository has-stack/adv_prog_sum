import os


def get_test_root() -> str:
    return os.environ["SMMU_TEST_ROOT"]


if __name__ == "__main__":
    print(get_test_root())
