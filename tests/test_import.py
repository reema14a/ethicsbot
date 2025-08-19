def test_import():
    import ethics_engine as ee
    assert hasattr(ee, "__version__")
