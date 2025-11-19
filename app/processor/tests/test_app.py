def test_import_processor():
    """Test that HLSSegmentProcessor can be imported from processor.app"""
    from processor.app import HLSSegmentProcessor

    assert HLSSegmentProcessor is not None
