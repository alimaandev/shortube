from shortube.core.types import MediaAsset


class ImageFallbackProvider:
    name = "fallback_images"

    def search(
        self,
        query: str,
        media_type: str = "image",
        orientation: str = "portrait",
        max_results: int = 3,
    ) -> list[MediaAsset]:
        return []
