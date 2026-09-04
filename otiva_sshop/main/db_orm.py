import asyncio

from main.models import MainBlocks, PageBlocks, MotivationBlocks, RegularQuestions


async def orm_get_regular_content(page_slug: str) -> dict:
    """
    Get regular content for page

    :return: dict["page": Page, "main_block": MainBlock, "blocks": list[PageBlocks]]
    """
    main_page_data = await MainBlocks.objects \
        .select_related("page") \
        .filter(page__slug=page_slug) \
        .aget()
    page = main_page_data.page
    page.title = f"Otiva - {page.title}"
    blocks = [block async for block in PageBlocks.objects.filter(page__slug=page_slug).order_by("display_order")]

    result = {
        "page": page,
        "main_block": main_page_data,
        "blocks": blocks,
    }
    return result


async def orm_get_main_index_content(page_slug: str) -> dict:
    """
    Get main index content for page
    :param page_slug:
    :return: dict["page": Page, "main_block": MainBlock, "blocks": list[PageBlocks], "motivation_block": MotivationBlock]
    """
    page_data, motivation_block = await asyncio.gather(
        orm_get_regular_content(page_slug),
        MotivationBlocks.objects.filter(page__slug=page_slug).order_by("?").afirst()
    )
    page_data["motivation_block"] = motivation_block
    return page_data


async def orm_get_about_content(page_slug: str) -> dict:
    """
        Get about content for page
        :param page_slug:
        :return: dict["page": Page, "main_block": MainBlock, "blocks": list[PageBlocks], "questions_answers": list[RegularQuestions]]
        """
    page_data = await orm_get_regular_content(page_slug)
    qas = [qa async for qa in RegularQuestions.objects.filter(page__slug=page_slug).order_by("display_order")]
    page_data["questions"] = qas
    return page_data
