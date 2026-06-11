import aiohttp
import json
import logging

logger = logging.getLogger('discord')

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Content-Type": "application/json",
    "Priority": "u=3, i",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Safari/605.1.15",
    "x-sauron-app-name": "sauron-search-results-app",
    "x-sauron-app-version": "e314886eb1"
}

class AutoTraderClient:
    def __init__(self):
        self.session = None

    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=HEADERS)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_listings(self, filters):
        """
        Fetches listings based on filters.
        Example filters: [{"filter":"make","selected":["Renault"]}, {"filter":"model","selected":["Megane"]}]
        """
        url = "https://www.autotrader.co.uk/at-gateway?opname=SearchResultsListingsGridQuery&opname=SearchResultsFacetsWithGroupsQuery"
        
        payload = [
            {
                "operationName": "SearchResultsListingsGridQuery",
                "variables": {
                    "filters": filters,
                    "channel": "cars",
                    "page": 1,
                    "sortBy": "relevance",
                    "listingType": None,
                    "searchId": "bot-search-id",
                    "featureFlags": ["USE_MULTI_CATEGORY_SEARCH"]
                },
                "query": "query SearchResultsListingsGridQuery($filters: [FilterInput!]!, $channel: Channel!, $page: Int, $sortBy: SearchResultsSort, $listingType: [ListingType!], $searchId: String!, $featureFlags: [FeatureFlag]) {\n  searchResults(\n    input: {facets: [], filters: $filters, channel: $channel, page: $page, sortBy: $sortBy, listingType: $listingType, searchId: $searchId, featureFlags: $featureFlags}\n  ) {\n    listings {\n      ... on SearchListing {\n        type\n        advertId\n        title\n        subTitle\n        attentionGrabber\n        price\n        vehicleLocation\n        images\n        dealerLink\n        badges {\n          type\n          displayText\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}"
            }
        ]

        session = await self.get_session()
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                try:
                    if isinstance(data, list) and len(data) > 0:
                        res_data = data[0].get('data', {})
                        if res_data is None:
                            logger.error(f"GraphQL Error in listings: {data[0].get('errors')}")
                            return []
                        
                        search_results = res_data.get('searchResults')
                        if search_results is None:
                            logger.error(f"searchResults is None. Response: {json.dumps(data)}")
                            return []

                        return search_results.get('listings', [])
                    return []
                except Exception as e:
                    logger.error(f"Failed to parse AutoTrader listings: {e}. Raw Data: {json.dumps(data)}")
                    return []
            else:
                text = await response.text()
                logger.error(f"AutoTrader API error fetching listings: {response.status}. Response: {text}")
                return []

    async def fetch_facets(self, advert_query):
        """
        Fetches facets and stock counts dynamically.
        Example advert_query: {"make": ["BMW"], "maxYear": "2026", "postcode": "sw1a1aa"}
        """
        url = "https://www.autotrader.co.uk/at-graphql?opname=SearchFormFacetsQuery"
        
        payload = [
            {
                "operationName": "SearchFormFacetsQuery",
                "variables": {
                    "advertQuery": advert_query,
                    "facets": ["distance", "make", "model"]
                },
                "query": "query SearchFormFacetsQuery($advertQuery: AdvertQuery!, $facets: [SearchFacetName]) {\n  search {\n    adverts(advertQuery: $advertQuery) {\n      advertList {\n        totalElements\n        __typename\n      }\n      facets(facets: $facets) {\n        name\n        values {\n          name\n          value\n          count\n          selected\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}"
            }
        ]

        session = await self.get_session()
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                try:
                    adverts_data = data[0]['data']['search']['adverts']
                    return {
                        "totalElements": adverts_data['advertList']['totalElements'],
                        "facets": adverts_data['facets']
                    }
                except (KeyError, IndexError, TypeError) as e:
                    logger.error(f"Failed to parse AutoTrader facets: {e}")
                    return None
            else:
                logger.error(f"AutoTrader API error: {response.status}")
                return None

    async def fetch_trims(self, make, model):
        """
        Fetches available trims for a given make and model.
        """
        url = "https://www.autotrader.co.uk/at-gateway?opname=SearchResultsFacetsWithGroupsQuery"
        
        filters = []
        if make:
            filters.append({"filter": "make", "selected": [make]})
        if model:
            filters.append({"filter": "model", "selected": [model]})
            
        # AutoTrader strictly requires price_search_type for this query
        filters.append({"filter": "price_search_type", "selected": ["total"]})
            
        payload = [
            {
                "operationName": "SearchResultsFacetsWithGroupsQuery",
                "variables": {
                    "filters": filters,
                    "channel": "cars",
                    "sortBy": "relevance",
                    "facets": ["acceleration_values","aggregated_trim","annual_tax_values","battery_charge_time_values","battery_quick_charge_time_values","battery_range_values","body_type","boot_size_values","category_tag","co2_emission_values","colour","digital_retailing","distance","doors_values","drivetrain","engine_power","engine_size","finance","fuel_consumption_values","fuel_type","insurance_group","is_manufacturer_approved","is_writeoff","keywords","lat_long","lease_in_stock","lease_product_type","leasing","make","mileage","model","monthly_price","ni_only","part_exchange_available","postcode","price","price_search_type","seats_values","seller_type","style","sub_style","transmission","ulez_compliant","with_digital_retailing","with_manufacturer_rrp_saving","year_manufactured"],
                    "facetGroups": ["acceleration","battery_range","body_type","boot_space","category_tag","charging_time","co2_emissions","colour","digital_retailing","distance","doors","drive_type","engine_power","engine_size","fuel_consumption","fuel_type","gearbox","insurance_group","keyword_search","lease_price_and_terms","make_and_model","mileage","monthly_price","previously_written_off","price","seats","seller_type","tax_per_year","year"],
                    "featureFlags": ["USE_MULTI_CATEGORY_SEARCH"]
                },
                "query": "query SearchResultsFacetsWithGroupsQuery($facets: [FacetName!]!, $filters: [FilterInput!]!, $channel: Channel!, $sortBy: SearchResultsSort, $facetGroups: [FacetGroupName!]!, $featureFlags: [FeatureFlag]) {\n  searchResults(\n    input: {facets: $facets, filters: $filters, channel: $channel, sortBy: $sortBy, featureFlags: $featureFlags}\n  ) {\n    sortBy {\n      selected\n      options {\n        name\n        value\n        descriptionTooltipText\n        __typename\n      }\n      __typename\n    }\n    facets {\n      facet\n      filters {\n        filter\n        options {\n          label\n          value\n          count\n          description\n          __typename\n        }\n        selected\n        isOnlySelected\n        sections {\n          label\n          values\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    facetGroups(facetGroupNames: $facetGroups, filters: $filters) {\n      facetGroupName\n      status\n      selectedValuesSummary\n      title\n      helpText\n      clearButtonLabel\n      __typename\n    }\n    filterPills(filters: $filters) {\n      filter\n      pills {\n        label\n        value\n        facetGroupName\n        __typename\n      }\n      __typename\n    }\n    suggestedFacets {\n      title\n      facetGroupName\n      __typename\n    }\n    page {\n      number\n      count\n      results {\n        count\n        __typename\n      }\n      __typename\n    }\n    finance {\n      hpGuideLink\n      pcpGuideLink\n      __typename\n    }\n    canSaveSearch\n    canSaveAdverts\n    __typename\n  }\n}"
            }
        ]

        session = await self.get_session()
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                try:
                    if isinstance(data, list) and len(data) > 0:
                        res_data = data[0].get('data', {})
                        if res_data is None:
                            logger.error(f"GraphQL Error: {data[0].get('errors')}")
                            return []
                        
                        search_results = res_data.get('searchResults')
                        if search_results is None:
                            logger.error(f"searchResults is None. Response: {json.dumps(data)}")
                            return []

                        facets = search_results.get('facets', [])
                        for facet in facets:
                            if facet.get('facet') == 'aggregated_trim':
                                options = facet.get('filters', [])[0].get('options', [])
                                return [opt['value'] for opt in options]
                    return []
                except Exception as e:
                    logger.error(f"Failed to parse AutoTrader trims: {e}. Raw Data: {data}")
                    return []
            else:
                logger.error(f"AutoTrader API error fetching trims: {response.status}")
                return []
