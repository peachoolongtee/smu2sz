# China reachability: model APIs and VM regions

Research for issue #6 (child of map #1). Checked on 2026-10-01.

**Status labels**
- **CONFIRMED** means an official vendor or primary source, linked inline.
- **UNVERIFIED** means plausible, but no official source was found.
- **ANECDOTAL** means third-party blogs, forum posts, vendor marketing or old measurements.

## Short answer

- **Claude cannot be called from a Hong Kong VM.** Hong Kong is not on Anthropic's supported-regions list. Singapore is.
- **DeepSeek can be called from Hong Kong or Singapore.** It publishes no caller-region restriction.
- **Hong Kong is closest to mainland visitors, and ICP filing is not needed** outside the mainland.
- **So no single VM gets all three:** Claude called directly, the lowest mainland latency, and no routing split.

## (a) Anthropic API: supported regions

| Claim | Status | Source |
| --- | --- | --- |
| Singapore is a supported region for commercial API access and Claude.ai. | CONFIRMED | [Supported regions (API docs)](https://platform.claude.com/docs/en/api/supported-regions); [Supported Regions Policy](https://www.anthropic.com/supported-countries) |
| Hong Kong is **not** listed, in either the API list or the Claude.ai list. | CONFIRMED | Same two pages. Macau is also absent. Taiwan is listed. |
| Mainland China is **not** listed. | CONFIRMED | Same two pages |
| The policy page is titled "Commercial API access and Claude.ai". It has two lists: "where we currently offer commercial API access" and "where we currently offer Claude.ai access". | CONFIRMED | [Supported Regions Policy](https://www.anthropic.com/supported-countries) |
| Calls from unsupported locations are rejected at the IP level, with an error like "Access to Anthropic models is not allowed from unsupported countries, regions, or territories". | ANECDOTAL | [openclaw issue #30672](https://github.com/openclaw/openclaw/issues/30672), Mar 2026. Cloudflare community threads report 403s when a Worker's outbound fetch exits via a Hong Kong edge. |
| Reaching Claude through AWS Bedrock with a Hong Kong account or connection does not work either. | ANECDOTAL | Third-party write-ups only, e.g. [hongkongaipodcast.com](https://hongkongaipodcast.com/blog/hk-ai-wall). Not checked against AWS docs. |

**Probe from the dev machine (location not recorded).** A keyless `GET https://api.anthropic.com/v1/models` returned `401 authentication_error` ("x-api-key header is required"). A 401 rather than a 403 suggests the region check passed from that machine. It says nothing about a Hong Kong VM.

## (b) DeepSeek API

| Claim | Status | Source |
| --- | --- | --- |
| Base URLs: `https://api.deepseek.com` (OpenAI-compatible) and `https://api.deepseek.com/anthropic` (Anthropic-compatible). | CONFIRMED | [DeepSeek API docs](https://api-docs.deepseek.com/) |
| Current models are **`deepseek-flash`** (V4.1 Flash, released 2026-09-10) and **`deepseek-v4-pro`**. Both have a 1M-token context and 384K maximum output. | CONFIRMED | [Models & pricing](https://api-docs.deepseek.com/quick_start/pricing); [change log](https://api-docs.deepseek.com/updates) |
| **`deepseek-chat` and `deepseek-reasoner` are legacy names.** The 2026-04-24 entry said they would be discontinued on 2026-07-24. Until then they pointed at V4-Flash. Do not build on them. | CONFIRMED | [Change log](https://api-docs.deepseek.com/updates) |
| `deepseek-v4-flash` and `deepseek-v4-flash-vision-exp` are still accepted, but they are served by V4.1 Flash. | CONFIRMED | [Models & pricing](https://api-docs.deepseek.com/quick_start/pricing) |
| V4-Pro has thinking-effort levels (low, high, max). Peak and off-peak pricing applies, with off-peak at half price. | CONFIRMED | [Change log](https://api-docs.deepseek.com/updates) (2026-08-13) |
| Both models support JSON output, tool calls, the Responses API and the Anthropic-format API. | CONFIRMED | [Models & pricing](https://api-docs.deepseek.com/quick_start/pricing) |
| JSON output is `response_format: {"type": "json_object"}`. The prompt must contain the word "json" and an example. The API "may occasionally return empty content". It enforces valid JSON, not a schema. | CONFIRMED | [JSON output guide](https://api-docs.deepseek.com/guides/json_mode) |
| DeepSeek documents **no JSON-schema or strict structured-output mode**. The function-calling guide did not mention a strict mode when fetched. | CONFIRMED (absence on the fetched pages) | [Function calling guide](https://api-docs.deepseek.com/guides/function_calling) |
| DeepSeek documents **no restriction by caller region**. The terms say only "We make no warranty that the Services are available… in certain jurisdictions". Export-control compliance is the developer's job. | CONFIRMED | [Open Platform Terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) (effective 2026-04-29) |
| The terms are governed by PRC mainland law. Developers must disclose to end users that output is AI-generated and "for reference only". Developers must also provide their own personal-data notice. | CONFIRMED | Same terms |
| DeepSeek stores personal data in the PRC. That privacy policy excludes downstream apps, which must write their own. | CONFIRMED | [Privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) (updated 2026-02-10) |
| The API is reachable worldwide with no IP blocking. | ANECDOTAL | Third-party pages, e.g. [theneuralbase.com](https://theneuralbase.com/deepseek/qna/deepseek-api-availability-and-regions/). Some governments ban DeepSeek on official devices; that does not apply here. |
| The API is reachable from mainland China. | UNVERIFIED (very likely) | DeepSeek is a Hangzhou company, and its mainland apps use the same service. |

**Probe from the dev machine.** A keyless `GET https://api.deepseek.com/models` returned `401 Authentication Fails` in about 0.14 s. It resolved to `3.173.21.63`, which looks like an AWS CloudFront address. This suggests a global CDN front, but that is an inference, not a documented fact.

**For the adapter.** The Anthropic-compatible endpoint means one Anthropic SDK client might serve both backends by swapping the base URL and model. That compatibility is CONFIRMED to exist; which features carry over was not tested. Since DeepSeek has no schema-strict mode, validate its JSON with Pydantic and retry on empty or invalid output.

## (c) Mainland visitors reaching Hong Kong and Singapore hosts

### ICP filing

| Claim | Status | Source |
| --- | --- | --- |
| ICP filing applies only to servers in the Chinese mainland, so a Hong Kong or Singapore VM needs none. Alibaba Cloud: "ICP filing applies only to servers located in the Chinese mainland." | CONFIRMED | [Alibaba Cloud ICP FAQ](https://www.alibabacloud.com/help/en/icp-filing/basic-icp-service/product-overview/faq-about-icp-filing-applications-in-different-scenarios); [What is ICP filing](https://www.alibabacloud.com/help/en/icp-filing/basic-icp-service/product-overview/what-is-an-icp-filing) |
| Tencent Cloud blocks mainland-hosted domains that lack filing. It says nothing that extends this to off-mainland regions. | CONFIRMED (for the mainland case) | [Tencent Cloud ICP support](https://www.tencentcloud.com/solutions/icp-registration-support) |
| A mainland CDN (e.g. Cloudflare China Network, or a mainland Alibaba or Tencent CDN) would require ICP. | UNVERIFIED | This follows from the rule above; the Cloudflare docs were not checked. |

### By provider

**Alibaba Cloud (Hong Kong or Singapore)**
- **CONFIRMED:** "BGP (Multi-ISP) Pro" EIPs route traffic over dedicated carrier lines "reducing access latency for users in the Chinese mainland". Source: [BGP Pro EIP doc](https://www.alibabacloud.com/help/en/eip/use-cases/use-bgp-pro-eips-to-access-web-services-with-low-network-latency).
  - They are available pay-as-you-go in China (Hong Kong), Singapore and five other Asian regions. Subscription billing is Hong Kong only.
  - The line type is fixed when the EIP is created.
  - The doc's own test (Hangzhou to Manila) shows total time falling from 0.459 s to 0.159 s. We found no Hong Kong-specific figure.
- **ANECDOTAL (academic, 2021):** a University of Maryland (Geneva) measurement from Nov–Dec 2021 found the GFW dynamically blocking "fully encrypted" proxy traffic to Alibaba Cloud Hong Kong and Singapore, Vultr and DigitalOcean. **TLS and HTTP were explicitly exempt**, so an HTTPS site is not the target. Source: [Geneva write-up](https://geneva.cs.umd.edu/posts/fully-encrypted-traffic/en/).

**Tencent Cloud (Hong Kong or Singapore)**
- **CONFIRMED:** Tencent's own doc says that for off-mainland Lighthouse regions, "access from the Chinese mainland may experience a significant delay and packet loss due to the ISP network lines". It also says the stated bandwidth is peak, "not considered a guaranteed service metric". Source: [Tencent Cloud Lighthouse regions and network connectivity](https://www.tencentcloud.com/document/product/1103/41266).
- **ANECDOTAL (vendor blog):** Tencent techpedia pages claim single-digit RTT from Hong Kong to the mainland.

**AWS (ap-east-1 Hong Kong or ap-southeast-1 Singapore)**
- **UNVERIFIED:** AWS publishes nothing on mainland reachability.
- **ANECDOTAL:** the 2021 Geneva measurement reported EC2 and Lightsail as *not* affected by the encrypted-traffic blocking.
- **UNVERIFIED:** AWS does not offer an optimised cross-border line product like Alibaba's BGP Pro in these regions.

**GCP (asia-east2 Hong Kong or asia-southeast1 Singapore)**
- **ANECDOTAL (Google Cloud Support forum reply, Nov 2017):** GCP does not restrict traffic from China, but "Google do not have any control over the GFW blocking methods". Source: [gce-discussion thread](https://groups.google.com/g/gce-discussion/c/oiPyWdmNAUs).
- **ANECDOTAL:** Google-owned hostnames (`*.appspot.com`, `*.google.com`, Firebase, Google Fonts or APIs) are blocked in the mainland.
  - A VM behind a custom domain avoids most of this, as long as the page itself loads nothing from Google.
  - We found no official source for blanket IP-range throttling of GCP. It is widely asserted but unconfirmed.

**Vercel (for comparison, since the handoff mentions it)**
- **CONFIRMED:** "China's network controls can block or throttle traffic to foreign domains, including Vercel's `.vercel.app` subdomains". Vercel "has no servers or CDN nodes in mainland China". Source: [Vercel KB](https://vercel.com/kb/guide/accessing-vercel-hosted-sites-from-mainland-china) (updated 2026-09-11).
- **ANECDOTAL:** GreatFire lists `vercel.app` as mostly blocked. Source: [GreatFire](https://en.greatfire.org/domain/vercel.app).

### Latency (all ANECDOTAL)

These figures come from hosting-vendor blogs such as [server.hk](https://server.hk/blog/hong-kong-vps-vs-singapore-vps-which-for-your-asia-pacific-app-in-2026/) and [jtti.cc](https://www.jtti.cc/supports/2909.html). We made no measurements of our own.

| Route | Typical RTT |
| --- | --- |
| Mainland to Hong Kong, ordinary BGP | About 10–60 ms. Southern China, including Shenzhen, sits at the low end. Evening peaks raise it and add loss. |
| Mainland to Hong Kong, optimised line (CN2 GIA, BGP Pro) | About 5–30 ms |
| Mainland to Singapore | About 40–80 ms on optimised lines; more with loss on ordinary routes at peak |

### Most reliable choice for mainland visitors

This is a judgement drawn from the sources above.
- **Hong Kong on Alibaba Cloud with a BGP (Multi-ISP) Pro EIP** is the only option with an official, documented mainland-optimised line in the right place. Second choices are Tencent Cloud Hong Kong and AWS ap-east-1.
- **Singapore also offers BGP Pro on Alibaba Cloud**, but the physics costs roughly 30–50 ms or more.
- **In every case:** use a custom domain, self-host fonts and scripts, load no Google, Vercel or other blocked third-party assets, and serve over HTTPS.

## (d) Does Anthropic restrict serving users in unsupported regions?

| Claim | Status | Source |
| --- | --- | --- |
| The Usage Policy forbids you to "Access or facilitate account or API access to Claude to persons, entities, or users in violation of our Supported Regions Policy" (under "Do Not Abuse our Platform"). | CONFIRMED | [Usage Policy](https://www.anthropic.com/legal/aup) (effective 2025-09-15) |
| The Supported Regions Policy lists where Anthropic "currently offer[s] commercial API access". It also reserves the right not to serve entities majority-owned from outside those regions. | CONFIRMED | [Supported Regions Policy](https://www.anthropic.com/supported-countries) |
| Since 2025-09-04, entities more than 50% owned, directly or indirectly, by companies headquartered in unsupported regions such as China are refused, wherever they operate. | CONFIRMED | [Anthropic announcement](https://www.anthropic.com/news/updating-restrictions-of-sales-to-unsupported-regions) |
| The Commercial Terms bar providing access "to persons or entities or into countries or for uses where it is prohibited under U.S. or other applicable international law" (§M.8). They do not otherwise say where end users may be. | CONFIRMED | [Commercial Terms](https://www.anthropic.com/legal/commercial-terms) (effective 2025-06-17) |
| Whether a mainland judge viewing a server-side Claude result "facilitates API access to users in violation of" the Supported Regions Policy. | **UNVERIFIED / unclear** | Neither the policy nor the announcement addresses downstream end users of a customer's app. The Usage Policy's wording ("users") could be read to cover them. Only Anthropic can settle this. |

In brief:
- A team account that is not majority-owned from an unsupported region, calling Claude from a Singapore VM, is plainly within policy. The team should confirm the account holder meets this.
- Letting mainland users trigger live Claude calls sits in a grey zone that the Usage Policy's wording arguably reaches.
- Serving cached Claude output, or routing mainland sessions to DeepSeek, avoids the question. This is a risk reading, not legal advice.

## Does the handoff's fallback cover the rules?

- **CONFIRMED:** a demo video of 5 minutes or less is a **required** deliverable anyway, alongside the technical document and the deck. Source code, the security self-assessment and execution evidence are optional. Source: the official 2026 site, via `SZ_Research/research/fintechathon_winners_2026-09-30/deep_dive.md`.
- **CONFIRMED:** task completion (40%) is scored on "scripted tasks in a simulated environment".
- **UNVERIFIED:** whether that harness drives **our live deployment** or the organisers' own environment, and from where. The site text does not say.
  - A recorded video plus cached results covers the review only if the harness does not need a live endpoint.
  - **Ask the organisers before 20 Oct:** do judges or the harness need a live URL, and do they access it from the mainland?

## Implications for the VM and routing decision

These are options and trade-offs; the decision is left to the parent.

1. **Singapore VM, both backends live.**
   - Pros: Claude is callable directly and in policy. One VM.
   - Cons: about 40–80 ms or more (ANECDOTAL) and more peak-hour loss for mainland visitors. The grey zone in (d) remains if mainland users trigger live Claude calls.
   - Mitigation: Alibaba Cloud Singapore with a BGP Pro EIP.
2. **Hong Kong VM, DeepSeek live, Claude never called from Hong Kong.**
   - Pros: best mainland latency (Alibaba Cloud HK with a BGP Pro EIP is the documented optimised path). No Claude policy issue.
   - Cons: Claude outputs must be precompiled (the cache) or dropped. Compiling with Claude happens off-box, e.g. on a dev machine in a supported region, with the results shipped as fixtures.
3. **Hong Kong VM for web and api, plus a small Singapore relay that holds the Anthropic key.**
   - Pros: mainland latency stays low. Claude stays live.
   - Cons: two VMs. The relay's egress is Singapore, which satisfies the IP check, but a Hong Kong box driving it could itself be read as circumventing the Supported Regions Policy. This is the most exposed option under (d).
4. **Routing by visitor origin (either VM).**
   - How: GeoIP or `Accept-Language` sends mainland sessions to DeepSeek or cached Claude output, and everyone else to live Claude.
   - Pros: sidesteps (d).
   - Cons: more code paths to test. The harness may appear as a mainland IP and get the DeepSeek path during scoring.
5. **Common to all options.**
   - Pin `deepseek-flash` or `deepseek-v4-pro`, not `deepseek-chat`.
   - Treat DeepSeek JSON as unvalidated.
   - Keep the cache as the ground truth for demo fixtures.
   - Do not use Vercel or GCP-branded hostnames.
   - Run a real reachability test from a mainland vantage point before 17 Oct. For example: `curl` timing from a friend in Shenzhen, or a mainland probe service such as 17ce or boce (UNVERIFIED that these suit us).
