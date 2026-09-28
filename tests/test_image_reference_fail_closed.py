from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openai import OpenAIError
from PIL import Image


@pytest.fixture
def renderer(tmp_path, monkeypatch):
    from src import image_concepts

    monkeypatch.setattr(image_concepts, "ROOT_DIR", tmp_path)
    return image_concepts


def test_missing_references_never_call_a_provider(renderer, monkeypatch):
    factory = Mock(side_effect=AssertionError("No provider allowed without references"))
    monkeypatch.setattr(renderer, "OpenAI", factory)
    with pytest.raises(ValueError, match="reference"):
        renderer._generate_image("synthetic product", [])
    factory.assert_not_called()


@pytest.mark.parametrize("failure", ["provider-error", "no-image-output"])
def test_failed_reference_generation_never_falls_back_to_unconditioned_image(
    renderer, tmp_path, monkeypatch, failure
):
    source = tmp_path / "owned.jpg"
    Image.new("RGB", (8, 8), "red").save(source)
    client = Mock()
    client.images.generate.return_value = SimpleNamespace(
        data=[SimpleNamespace(b64_json="unconditioned-image-must-not-be-used")]
    )
    monkeypatch.setattr(renderer, "OpenAI", lambda: client)
    if failure == "provider-error":
        client.responses.create.side_effect = OpenAIError("synthetic provider failure")
    else:
        client.responses.create.return_value = SimpleNamespace(output=[])
    with pytest.raises(RuntimeError, match="reference"):
        renderer._generate_image("synthetic product", [source])
    client.images.generate.assert_not_called()


def test_successful_generation_sends_the_selected_reference(renderer, tmp_path, monkeypatch):
    source = tmp_path / "owned.jpg"
    Image.new("RGB", (8, 8), "red").save(source)
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output=[SimpleNamespace(type="image_generation_call", result="synthetic-image")]
    )
    monkeypatch.setattr(renderer, "OpenAI", lambda: client)
    assert renderer._generate_image("synthetic product", [source]) == "synthetic-image"
    content = client.responses.create.call_args.kwargs["input"][0]["content"]
    assert content[1]["image_url"] == renderer._data_url(source)
    client.images.generate.assert_not_called()


def test_unreadable_reference_stops_instead_of_silently_dropping_it(renderer, tmp_path):
    good, bad = tmp_path / "good.png", tmp_path / "bad.png"
    Image.new("RGB", (8, 8), "red").save(good)
    bad.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="reference"):
        renderer._prepare_references([good, bad])


def test_reference_cache_cannot_replace_another_products_image(renderer, tmp_path):
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    Image.new("RGB", (8, 8), "red").save(first)
    Image.new("RGB", (8, 8), "blue").save(second)
    first_output = renderer._prepare_references([first])[0]
    saved = first_output.read_bytes()
    second_output = renderer._prepare_references([second])[0]
    assert first_output != second_output
    assert first_output.read_bytes() == saved
    assert renderer._prepare_references([first])[0] == first_output
    assert all(Path(path).is_file() for path in (first_output, second_output))


def test_all_concept_images_are_decoded_before_paid_generation(renderer, tmp_path, monkeypatch):
    good, bad = tmp_path / "owned.png", tmp_path / "broken.png"
    Image.new("RGB", (8, 8), "red").save(good)
    bad.write_bytes(b"not an image")
    monkeypatch.setattr(renderer, "AI_IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr(renderer, "IMAGE_CONCEPT_COUNT", 2)
    monkeypatch.setattr(renderer, "OUTPUTS_DIR", tmp_path / "outputs")
    generation = Mock()
    monkeypatch.setattr(renderer, "_generate_image", generation)
    with pytest.raises(ValueError, match="reference"):
        renderer.generate_image_concepts({"image_concepts": [
            {"source_asset_hint": good.name}, {"source_asset_hint": bad.name},
        ]}, [good, bad])
    generation.assert_not_called()
