def test_src_root(src_root):
    print(src_root)
    assert (src_root / "test").is_dir()


def test_test_root(test_root):
    assert test_root.is_dir()
