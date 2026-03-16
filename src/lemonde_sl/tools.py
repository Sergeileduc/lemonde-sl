TRANSPARENT_GIF = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="

HEAVY_ATTRS = [
    "srcset",
    "data-srcset",
    "sizes",
    "data-sizes",
    "data-src",
    "width",
    "height",
    "loading",
    "decoding",
]


def neutralize_img(img):
    # Supprimer tous les attributs lourds
    for attr in HEAVY_ATTRS:
        img.attrs.pop(attr, None)

    # Supprimer src pour éviter tout chargement
    img.attrs.pop("src", None)

    # Ajouter un placeholder minimal
    img["src"] = TRANSPARENT_GIF


def iter_children(node):
    child = node.child
    while child:
        yield child
        child = child.next


def pick_best_src(srcset: str, target_width: int = 664) -> str | None:
    """
    Choisit l'URL du srcset la plus proche de target_width.
    """
    candidates = []
    for entry in srcset.split(","):
        parts = entry.strip().split(" ")
        if len(parts) != 2:
            continue
        url, width = parts
        try:
            width = int(width.rstrip("w"))  # type: ignore
            candidates.append((width, url))
        except ValueError:
            continue

    if not candidates:
        return None

    # Choisir la largeur la plus proche
    best = min(candidates, key=lambda x: abs(x[0] - target_width))  # type: ignore
    return best[1]


def fix_image_urls(soup: "BeautifulSoup", target_width: int = 664) -> None:
    """
    Normalize <img> URLs by selecting the best source from srcset or data-srcset.

    This function processes standalone <img> tags (i.e., not inside <picture>).
    It extracts the most appropriate image URL from:
        - img["srcset"]
        - img["data-srcset"]
    using the closest width to `target_width`.

    If no srcset is available, it falls back to:
        - img["data-src"]

    After selecting the best URL, the function:
        - Sets img["src"] to the chosen URL.
        - Removes responsive attributes that PDF generators do not support:
              srcset, sizes, width, height, data-src, data-srcset

    Args:
        soup (BeautifulSoup):
            Parsed HTML document or subtree.
        target_width (int):
            Desired width to select from the srcset. Defaults to 664.

    Returns:
        None: The soup is modified in place.
    """
    for img in soup.select("img"):
        # Skip images already handled by simplify_picture_tags()
        if img.parent and img.parent.name == "picture":
            continue

        # 1) srcset or data-srcset
        srcset: str = img.get("srcset") or img.get("data-srcset") or img.get("data-lazy-srcset")  # type: ignore[assignment]
        if srcset:
            best = pick_best_src(srcset, target_width)
            if best:
                img["src"] = best

        # 2) fallback: data-src
        elif img.get("data-src") or img.get("data-lazy-src"):
            img["src"] = img.get("data-src") or img.get("data-lazy-src")  # type: ignore[assignment]

        # 3) remove useless attributes
        for attr in (
            "srcset",
            "sizes",
            "width",
            "height",
            "data-src",
            "data-srcset",
            "data-lazy-src",
            "data-lazy-srcset",
        ):
            img.attrs.pop(attr, None)


def simplify_picture_tags(soup: "BeautifulSoup", target_width: int = 664) -> None:
    """
    Simplify <picture> elements by extracting the best <img> source and removing
    responsive attributes.

    This function:
      - Finds all <picture> tags.
      - Extracts the nested <img>.
      - Chooses the best image URL from `srcset` or `data-srcset` using the
        closest width to `target_width`.
      - Falls back to `data-src` if no srcset is available.
      - Removes responsive attributes (`srcset`, `sizes`, `width`, `height`,
        `data-src`, `data-srcset`).
      - Replaces the entire <picture> with a single clean <img> tag.

    Args:
        soup (BeautifulSoup): Parsed HTML document.
        target_width (int): Desired width to select from the srcset.

    Returns:
        None: The soup is modified in place.
    """
    for picture in soup.select("picture"):
        img = picture.find("img")
        if not img:
            continue

        # 1) srcset or data-srcset
        srcset: str = img.get("srcset") or img.get("data-srcset") or img.get("data-lazy-srcset")  # type: ignore[assignment]
        if srcset:
            best = pick_best_src(srcset, target_width)
            if best:
                img["src"] = best

        # 2) fallback: data-src
        elif img.get("data-src") or img.get("data-lazy-src"):
            img["src"] = img.get("data-src") or img.get("data-lazy-src")  # type: ignore[assignment]

        # 3) remove useless attributes
        for attr in ("srcset", "sizes", "width", "height", "data-src", "data-srcset"):
            img.attrs.pop(attr, None)

        # 4) replace <picture> with <img>
        picture.replace_with(img)


def limit_images_with_priority(soup: "BeautifulSoup", max_global: int = 50) -> None:
    """
    Limite le nombre total d'images en donnant la priorité aux images d'article.
    Les images de portfolio ne sont gardées que s'il reste du budget.
    """

    # 1) Séparer les deux types d'images
    article_figs = soup.select("figure:not(.portfolio__figure)")
    portfolio_figs = soup.select("figure.portfolio__figure")

    # 2) Compter les images article
    article_imgs = []
    for fig in article_figs:
        img = fig.find("img")
        if img:
            article_imgs.append(img)

    # 3) Si les images article dépassent déjà le max, on garde juste les premières
    if len(article_imgs) >= max_global:
        # Neutraliser toutes les images article au-delà du quota
        for img in article_imgs[max_global:]:
            neutralize_img(img)
        # Et neutraliser toutes les images portfolio
        for fig in portfolio_figs:
            media = fig.select_one("section.portfolio__media-wrapper")
            if media:
                media.decompose()
        return

    # 4) Sinon, il reste du budget pour le portfolio
    remaining = max_global - len(article_imgs)

    # 5) Garder seulement les `remaining` premières images du portfolio
    for fig in portfolio_figs[remaining:]:
        media = fig.select_one("section.portfolio__media-wrapper")
        if media:
            media.decompose()


# DEPRECATE. Keep for Legacy
def limit_portfolio_images(soup: "BeautifulSoup", max_images: int = 5) -> None:
    """
    Garde seulement les `max_images` premières figures du portfolio.
    Supprime les autres pour éviter les OOM.
    """
    figures = soup.select("figure.portfolio__figure")
    for fig in figures[max_images:]:
        try:
            img = fig.select_one("section.portfolio__media-wrapper")
            if img:
                img.decompose()
        except Exception:
            pass

def sanitize_images(soup: "BeautifulSoup", max_img: int = 3) -> None:
    imgs = soup.select("img")

    for i, img in enumerate(imgs):
        if i < max_img:
            continue
        neutralize_img(img)

if __name__ == "__main__":
    srcset = """
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/320/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 320w,  
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/556/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 556w,  
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/640/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 640w,  
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/664/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 664w,  
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/960/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 960w,   
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/1112/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 1112w,  
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/1328/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 1328w,  
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/1668/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 1668w,   
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/1992/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 1992w,  
        https://img.lemde.fr/2026/02/25/0/0/5064/3373/2301/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 2301w,  
        """  # noqa: E501, W291

    best = pick_best_src(srcset, target_width=650)
    print(best)

    html = """
    <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body>
            <section id="habillagepub" class="article article--single article--iso article--content "> 
<section class="zone zone--article  zone--article-premium zone--article-opinion zone--article-offer 
old__zone">                          <header class="article__header article__header--opinion ">         
<h1 class="article__title article__title--opinion">«&nbsp;Donald Trump est le président de l’instabilité 
et de l’incertain, mais de plus en plus à ses dépens&nbsp;»</h1> <section class="article__authors">  <h2 
class="article__opinion-type"> <a class="article__section" href="/idees-chroniques/">Chronique</a> </h2>  
<a class="article__author article__author-link" href="/signataires/gilles-paris/">   <img 
class="article__author-picture" src="https://img.lemde.fr/2017/09/22/0/0/0/0/108/108/60/0/f2df5fa_237.jpg"
alt="auteur" width="54" height="54">  <section class="article__author-description "> <p 
class="article__author-identity">Gilles Paris</p>  <p class="article__author-job">Editorialiste au 
«&nbsp;Monde&nbsp;»</p>  </section>  </a>  </section>  <p class="article__desc article__desc--opinion">A 
force de s’affranchir des règles, d’éructer face aux institutions et de conduire seul son pays vers une 
nouvelle guerre, le président des Etats-Unis ne témoigne que de son inaptitude à se comporter comme un 
homme d’Etat, relève Gilles Paris, éditorialiste au «&nbsp;Monde&nbsp;», dans sa chronique.</p>  <p 
class="meta meta__publisher meta__publisher--opinion"> <span class="meta__date">Publié aujourd’hui à 
09h02, modifié à 11h46</span>  <span class="meta__reading-time meta__reading-time--opinion"> <span 
class="icon__reading-time icon__reading-time--opinion"></span> <span><span class="sr-only">Temps de 
</span>Lecture 3 min.</span> </span>   <a class="meta__article-en-fr-url js-lang-switcher" 
href="/en/opinion/article/2026/02/25/trump-is-the-president-of-instability-and-uncertainty-increasingly-to
-his-own-detriment_6750862_23.html" hreflang="en"> <span class="meta__article-en-fr-url-link">Read in 
English</span> </a>  </p>                              <p class="ds-article-status 
ds-article-status--premium ds-article-status--opinion ds-article-status--subscriber " 
data-tracking="article-status">       <svg class="icon__svg ds-article-status__icon" 
xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 16 16"> <rect 
width="16" height="16" fill="#ffd644" rx="2"></rect> <path fill="#000" fill-opacity=".65" 
fill-rule="evenodd" d="M13.732 4.412c-.542.328-.723.77-.723 1.455v5.463c0 
.344.042.5.223.6l.18.1.5-.3.166.343-1.734 
1.07-.597-.414c-.264-.185-.375-.414-.375-.856V6.994c0-.912.278-1.398.666-1.697l.223-.171-1.638-.985-.735.4
56v7.105c0 .599-.083.685-.597.955 0 
0-.402.2-.956.5h-.111V5.283c0-.385-.043-.471-.25-.642l-.583-.485-.708.413v4.08c0 .713-.11 1.227-.665 
1.583l-1.388.9-.14-.243c.432-.343.528-.828.528-1.399V5.325c0-.613-.082-.856-.707-.741-.236.042-.597.1-.819
.128-.916.128-1.304-.542-.68-1.384 0 0 .153-.214.541-.728l.306.215-.222.328c-.291.428-.056.656.416.485a39 
39 0 0 0 .957-.386c1.318-.527 1.804.343 1.873.857l1.638-1.013 1.414 1.112 1.748-1.112 
1.346.785c.458.27.68.156 1-.015l.263-.143.208.357zm-8.56 
8.745c-.14-.4-.542-.813-1.263-.842-.68-.014-1.652.257-2.456.885L1.3 13c.583-.656 1.943-1.712 
3.371-1.726.75 0 1.277.257 1.652.67l.625-.356.18.37z" clip-rule="evenodd"></path> </svg>   <span 
class="ds-article-status__text">Article réservé aux abonnés</span> </p>   </header>       <section 
class="article__wrapper  article__wrapper--premium "> <article class="article__content 
old__article-content-single">                    <figure class="article__media"> <picture 
class="article__media"> <img 
src="https://img.lemde.fr/2026/02/25/0/0/5064/3373/664/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg
" alt="Donald Trump, au Capitole, à&nbsp;Washington, le 24&nbsp;février&nbsp;2026." srcset=" 
https://img.lemde.fr/2026/02/25/0/0/5064/3373/320/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
320w,  
https://img.lemde.fr/2026/02/25/0/0/5064/3373/556/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
556w,  
https://img.lemde.fr/2026/02/25/0/0/5064/3373/640/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
640w,  
https://img.lemde.fr/2026/02/25/0/0/5064/3373/664/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
664w,  
https://img.lemde.fr/2026/02/25/0/0/5064/3373/960/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
960w,   
https://img.lemde.fr/2026/02/25/0/0/5064/3373/1112/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
1112w,  
https://img.lemde.fr/2026/02/25/0/0/5064/3373/1328/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
1328w,  
https://img.lemde.fr/2026/02/25/0/0/5064/3373/1668/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
1668w,   
https://img.lemde.fr/2026/02/25/0/0/5064/3373/1992/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
1992w,  
https://img.lemde.fr/2026/02/25/0/0/5064/3373/2301/0/75/0/0e52036_ftp-1-6t4iezecnkyp-5287830-01-06.jpg 
2301w,  " sizes="(min-width: 1024px) 664px, (min-width: 768px) 664px, 100vw" width="664" height="443"> 
</picture>   <figcaption class="article__legend" aria-hidden="true">Donald Trump, au Capitole, 
à&nbsp;Washington, le 24&nbsp;février&nbsp;2026.  <span class="article__credit" aria-hidden="true">KENNY 
HOLSTON/«&nbsp;THE NEW YORK TIMES&nbsp;» VIA AFP</span>  </figcaption>  </figure>                      <p 
class="article__paragraph  "><span class="article__inner">L</span>a chorégraphie est convenue. Le 
président des Etats-Unis s’avance sous les vivats de ses troupes, après avoir été dûment annoncé par le 
sergent d’armes de la Chambre des représentants. Puis il assure que la situation du pays est bien 
meilleure depuis qu’il est aux affaires, salue la présence, dans les tribunes, des invités choisis pour 
illustrer son propos, pendant que son opposition fait savoir qu’elle pense rigoureusement le 
contraire.</p>                                      <section class="catcher catcher--favoris"> <div 
class="catcher__content"><span class="catcher__title catcher__title--hide">Lire aussi |</span><span 
class="catcher__desc">  <span class="icon__premium"><span class="sr-only">Article réservé à nos 
abonnés</span></span>  <a 
href="https://www.lemonde.fr/international/article/2026/02/25/diviseur-en-chef-devant-le-congres-donald-tr
ump-dessine-une-amerique-qui-n-en-finirait-pas-de-gagner_6668168_3210.html" class="js-article-read-also 
catcher--favoris__link" data-premium="1" id="article-title-3460807">Donald Trump dessine, dans son 
discours devant le Congrès, une Amérique qui n’en finirait pas de «&nbsp;gagner&nbsp;»</a> </span> </div> 
</section>                         <p class="article__paragraph  ">Le discours sur l’état de l’Union, 
prononcé mardi 24&nbsp;février par Donald Trump, a respecté<strong> </strong>la forme, sans dissiper une 
sourde inquiétude de fond. Cette dernière concerne autant les inconnues d’une nouvelle guerre contre 
l’Iran, dont il n’était absolument pas question il y a encore deux mois, que la consistance de la 
politique suivie par la Maison Blanche et la solidité des institutions des Etats-Unis. Un an après son 
retour, Donald Trump reste le président de l’instabilité et de l’incertain, mais de plus en plus à ses 
dépens, <a 
href="https://www.lemonde.fr/idees/article/2026/02/20/a-minneapolis-l-ice-s-est-heurte-a-une-histoire-poli
tique-suffisamment-dense-pour-produire-un-rapport-de-force_6667510_3232.html">comme </a><a 
href="https://www.lemonde.fr/idees/article/2026/02/20/a-minneapolis-l-ice-s-est-heurte-a-une-histoire-poli
tique-suffisamment-dense-pour-produire-un-rapport-de-force_6667510_3232.html">l’a déjà montré</a> <a 
href="https://www.lemonde.fr/idees/article/2026/02/20/a-minneapolis-l-ice-s-est-heurte-a-une-histoire-poli
tique-suffisamment-dense-pour-produire-un-rapport-de-force_6667510_3232.html">son recul concernant les 
méthodes brutales de la police des frontières</a>.</p>                <div id="inread_top" class="dfp-slot
dfp__slot dfp__inread dfp-unloaded" data-format="inread_top" aria-hidden="true"></div>          <p 
class="article__paragraph  ">Une attaque contre un régime iranien muré dans ses obstinations apparaît 
inévitable, compte tenu des moyens militaires massés à proximité des côtes iraniennes. Si elle intervient,
ce sera sans que le Congrès ait eu son mot à dire, alors qu’il est le seul habilité par la Constitution à 
déclarer la guerre, et sans que les buts de celle-ci aient été définis et présentés au préalable à 
l’opinion publique américaine. Le peuple, dont on se gargarise à la Maison Blanche, est prié d’opiner sans
avoir rien à redire. Avec Donald Trump, le «&nbsp;brouillard de guerre&nbsp;» devient la guerre à pile ou 
face, en fonction de l’instant.</p>                                      <section class="catcher 
catcher--favoris"> <div class="catcher__content"><span class="catcher__title catcher__title--hide">Lire 
aussi l’éditorial du «&nbsp;Monde&nbsp;» |</span><span class="catcher__desc">  <a 
href="https://www.lemonde.fr/idees/article/2026/02/24/trump-et-l-iran-les-menaces-et-les-interrogations_66
68047_3232.html" class="js-article-read-also catcher--favoris__link" data-premium="" 
id="article-title-3460172">Trump et l’Iran&nbsp;: les menaces et les interrogations</a> </span> </div>    
</section>                         <p class="article__paragraph  ">Le précédent du Venezuela plaide pour 
des frappes limitées forçant le régime iranien à des concessions auxquelles il se refuse aujourd’hui. Sur 
le papier, il s’agirait donc d’une guerre courte, de bombardements intenses sur des centres nerveux du 
régime, suivis de négociations dont Donald Trump pourrait présenter le résultat comme une victoire. Il 
reste que l’escalade pour la désescalade suppose que l’adversaire se conforme docilement à ce plan. Rien 
ne le garantit. Téhéran sait que la base électorale de Donald Trump n’acceptera aucun nouvel enlisement au
Moyen-Orient, qu’elle analysera comme un parjure.</p>                     <p class="article__paragraph  
">L’incertitude n’est pas que moyen-orientale. Les diatribes de Donald Trump, après l’annulation par la 
Cour suprême, le 20&nbsp;février, de droits de douane imposés au mépris de la Constitution et des pouvoirs
du Congrès, <a 
href="https://www.lemonde.fr/idees/article/2026/02/21/droits-de-douane-un-desaveu-cinglant-pour-donald-tru
mp_6667712_3232.html">doivent également alarmer</a>. Tout comme les propos désobligeants envers des juges 
qualifiés d’agents de l’étranger, dont certains ont assisté au discours sur l’état de l’Union. La 
précipitation à imposer de nouvelles taxes, sur des bases tout aussi fragiles, montre que le président des
Etats-Unis reste viscéralement hostile à la notion même de contre-pouvoir.</p>                            
<p class="article__paragraph  ">Aucun de ses prédécesseurs n’avait ainsi éructé après un revers devant la 
plus haute instance judiciaire des Etats-Unis, revers dont il était l’unique responsable. Cette gifle 
devrait renvoyer Donald Trump vers le Congrès, seul habilité à statuer durablement en la matière, mais 
l’étroitesse des majorités républicaines à la Chambre et au Sénat obligerait alors à négocier avec le camp
démocrate, qui fut pourtant par le passé le parti du protectionnisme. Et Donald Trump en est profondément 
incapable.</p>                    <h2 class="article__sub-title">Le poison du doute</h2>                  
<p class="article__paragraph  ">Cette inaptitude à se comporter comme un homme d’Etat se traduit déjà par 
une pression sans précédent sur les élections de mi-mandat, prévues en novembre et qui sont 
traditionnellement défavorable au parti qui occupe la Maison Blanche. Cette pression s’est tout d’abord 
manifestée par les tentatives de charcutage électoral, notamment au Texas, sans attendre le recensement 
décennal qui fournit ordinairement les arguments requis pour continuer de retirer tout enjeu dans 
l’écrasante majorité des districts électoraux.</p>                     <p class="article__paragraph  
">Environ 390&nbsp;districts sur 435&nbsp;sont en effet découpés scientifiquement pour que le résultat 
soit conforme aux attentes. Cet empressement n’a pas été très fructueux, car les démocrates y ont répondu 
par des redécoupages similaires <a 
href="https://www.lemonde.fr/international/article/2025/11/05/en-californie-gavin-newsom-remporte-son-pari
-et-obtient-des-electeurs-un-redecoupage-electoral-favorable-aux-democrates_6652069_3210.html">dans les 
Etats qu’ils contrôlent, comme en Californie</a>. Ces autres charcutages ont potentiellement effacé les 
gains espérés par Donald Trump.</p>                     <p class="article__paragraph  ">Cette riposte, là 
aussi, aurait dû conduire le locataire de la Maison Blanche à reconnaître les limites de son pouvoir. Il a
au contraire renchéri en avançant l’hypothèse d’une «&nbsp;nationalisation&nbsp;» des élections, alors 
qu’elles relèvent des Etats. Le président a évoqué quinze d’entre eux dans lesquels il souhaiterait 
intervenir avec les résultats qu’on imagine. Il s’est abstenu de les nommer, mais on peut penser qu’il 
s’agit d’Etats pivots où les républicains redoutent d’essuyer des défaites.</p>                     <p 
class="article__paragraph  ">Donald Trump s’inscrit dans une longue tradition républicaine visant à 
réduire la participation électorale dans les bastions démocrates. Paul Weyrich, membre fondateur du cercle
de réflexion influent Heritage Foundation, l’avait théorisée en&nbsp;1980, lors d’un rassemblement de la 
droite religieuse. Dans une tirade restée célèbre, il assurait que l’influence politique républicaine 
montait au fur et à mesure que la participation diminuait. Avec Donald Trump, un palier a cependant été 
franchi. Depuis une décennie, il ne cesse de répandre sur le vote le poison du doute, alors qu’il s’agit 
de l’acte citoyen autour duquel tout s’organise. Le précédent de la présidentielle de 2020, dont il n’a 
toujours pas accepté les résultats, invite à la vigilance.</p>                     <p 
class="article__paragraph  ">L’imprévisibilité de Donald Trump traduisait initialement sa volonté de 
s’affranchir des règles jusqu’alors admises pour imposer ses idées. Elle devient de plus en plus celle 
d’un homme qui se débat, et dont on s’écarte pour éviter d’être emporté avec lui.</p>                     
<section class="catcher catcher--favoris"> <div class="catcher__content"><span class="catcher__title 
catcher__title--hide">Lire aussi la tribune |</span><span class="catcher__desc">  <span 
class="icon__premium"><span class="sr-only">Article réservé à nos abonnés</span></span>  <a 
href="https://www.lemonde.fr/idees/article/2026/02/22/droits-de-douane-donald-trump-vient-d-en-faire-l-ame
re-experience-aux-etats-unis-la-loi-c-est-le-roi_6667820_3232.html" class="js-article-read-also 
catcher--favoris__link" data-premium="1" id="article-title-3460445">Droits de douane&nbsp;: «&nbsp;Donald 
Trump vient d’en faire l’amère expérience&nbsp;: aux Etats-Unis, la loi, c’est le roi&nbsp;»</a> </span> 
</div>    </section>                          <section class="author">    <p 
class="article__author-container"> <span class="author__detail"><a class="article__author-link" 
href="/signataires/gilles-paris/"> <span class="author__name">Gilles Paris</span><span 
class="author__desc">&nbsp;(Editorialiste au «&nbsp;Monde&nbsp;»)</span></a></span></p>    </section>     
</article> <footer class="article__footer-single old__article-footer">           <section 
class="lazy-forecast"></section>   </footer>  </section>            <div class="lazy-bizdev" 
data-url="idees" data-position="desktopFooter" data-service=""></div>  </section> </section>
        </body>
        </html>
    """  # noqa: E501, W291

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, features="html.parser")

    simplify_picture_tags(soup, target_width=650)

    print(soup.prettify())
