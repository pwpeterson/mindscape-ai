import { redirect } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

/**
 * Default ConPort landing page.
 *
 * Note: In the current UI mapping, the left-nav label "Now" points to `/conport/dashboard`.
 * We redirect `/conport` here so users land on the "Now" panel by default.
 */
export const load: PageLoad = ({ url }) => {
    throw redirect(302, `/conport/dashboard${url.search}`);
};
