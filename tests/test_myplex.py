# -*- coding: utf-8 -*-
import pytest
from plexapi.exceptions import BadRequest, NotFound
from plexapi.myplex import MyPlexInvite

from . import conftest as utils
from .payloads import MYPLEX_INVITE


def test_myplex_accounts(account, plex):
    assert account, "Must specify username, password & resource to run this test."
    print("MyPlexAccount:")
    print("username: %s" % account.username)
    print("email: %s" % account.email)
    print("home: %s" % account.home)
    print("queueEmail: %s" % account.queueEmail)
    assert account.username, "Account has no username"
    assert account.authenticationToken, "Account has no authenticationToken"
    assert account.email, "Account has no email"
    assert account.home is not None, "Account has no home"
    assert account.queueEmail, "Account has no queueEmail"
    account = plex.account()
    print("Local PlexServer.account():")
    print("username: %s" % account.username)
    # print('authToken: %s' % account.authToken)
    print("signInState: %s" % account.signInState)
    assert account.username, "Account has no username"
    assert account.authToken, "Account has no authToken"
    assert account.signInState, "Account has no signInState"


def test_myplex_resources(account):
    assert account, "Must specify username, password & resource to run this test."
    resources = account.resources()
    for resource in resources:
        name = resource.name or "Unknown"
        connections = [c.uri for c in resource.connections]
        connections = ", ".join(connections) if connections else "None"
        print("%s (%s): %s" % (name, resource.product, connections))
    assert resources, "No resources found for account: %s" % account.name


def test_myplex_connect_to_resource(plex, account):
    servername = plex.friendlyName
    for resource in account.resources():
        if resource.name == servername:
            break
    assert resource.connect(timeout=10)


def test_myplex_devices(account):
    devices = account.devices()
    for device in devices:
        name = device.name or "Unknown"
        connections = ", ".join(device.connections) if device.connections else "None"
        print("%s (%s): %s" % (name, device.product, connections))
    assert devices, "No devices found for account: %s" % account.name


def test_myplex_device(account, plex):
    assert account.device(plex.friendlyName)


def _test_myplex_connect_to_device(account):
    devices = account.devices()
    for device in devices:
        if device.name == "some client name" and len(device.connections):
            break
    client = device.connect()
    assert client, "Unable to connect to device"


def test_myplex_users(account):
    users = account.users()
    if not len(users):
        return pytest.skip("You have to add a shared account into your MyPlex")
    print("Found %s users." % len(users))
    user = account.user(users[0].title)
    print("Found user: %s" % user)
    assert user, "Could not find user %s" % users[0].title

    assert (
        len(users[0].servers[0].sections()) > 0
    ), "Couldn't info about the shared libraries"


def test_myplex_resource(account, plex):
    assert account.resource(plex.friendlyName)


def test_myplex_webhooks(account):
    if account.subscriptionActive:
        assert isinstance(account.webhooks(), list)
    else:
        with pytest.raises(BadRequest):
            account.webhooks()


def test_myplex_addwebhooks(account):
    if account.subscriptionActive:
        assert "http://example.com" in account.addWebhook("http://example.com")
    else:
        with pytest.raises(BadRequest):
            account.addWebhook("http://example.com")


def test_myplex_deletewebhooks(account):
    if account.subscriptionActive:
        assert "http://example.com" not in account.deleteWebhook("http://example.com")
    else:
        with pytest.raises(BadRequest):
            account.deleteWebhook("http://example.com")


def test_myplex_optout(account_once):
    def enabled():
        ele = account_once.query("https://plex.tv/api/v2/user/privacy")
        lib = ele.attrib.get("optOutLibraryStats")
        play = ele.attrib.get("optOutPlayback")
        return bool(int(lib)), bool(int(play))

    account_once.optOut(library=True, playback=True)
    utils.wait_until(lambda: enabled() == (True, True))
    account_once.optOut(library=False, playback=False)
    utils.wait_until(lambda: enabled() == (False, False))


@pytest.mark.authenticated
@pytest.mark.xfail(reason="Test account is missing online media sources?")
def test_myplex_onlineMediaSources_optOut(account):
    onlineMediaSources = account.onlineMediaSources()
    for optOut in onlineMediaSources:
        if optOut.key == 'tv.plex.provider.news':
            # News is no longer available
            continue

        optOutValue = optOut.value
        optOut.optIn()
        assert optOut.value == 'opt_in'
        optOut.optOut()
        assert optOut.value == 'opt_out'
        if optOut.key == 'tv.plex.provider.music':
            with pytest.raises(BadRequest):
                optOut.optOutManaged()
        else:
            optOut.optOutManaged()
            assert optOut.value == 'opt_out_managed'
        # Reset original value
        optOut._updateOptOut(optOutValue)

    with pytest.raises(NotFound):
        onlineMediaSources[0]._updateOptOut('unknown')


def test_myplex_inviteFriend(account, plex, mocker):
    inv_user = "hellowlol"
    vid_filter = {"contentRating": ["G"], "label": ["foo"]}
    secs = plex.library.sections()

    ids = account._getSectionIds(plex.machineIdentifier, secs)
    mocker.patch.object(account, "_getSectionIds", return_value=ids)
    with utils.callable_http_patch():
        account.inviteFriend(
            inv_user,
            plex,
            secs,
            allowSync=True,
            allowCameraUpload=True,
            allowChannels=False,
            filterMovies=vid_filter,
            filterTelevision=vid_filter,
            filterMusic={"label": ["foo"]},
        )

        assert inv_user not in [u.title for u in account.users()]


def test_myplex_acceptInvite(account, requests_mock):
    url = MyPlexInvite.REQUESTS
    requests_mock.get(url, text=MYPLEX_INVITE)
    invite = account.pendingInvite('testuser', includeSent=False)
    with utils.callable_http_patch():
        account.acceptInvite(invite)


def test_myplex_cancelInvite(account, requests_mock):
    url = MyPlexInvite.REQUESTED
    requests_mock.get(url, text=MYPLEX_INVITE)
    invite = account.pendingInvite('testuser', includeReceived=False)
    with utils.callable_http_patch():
        account.cancelInvite(invite)


def test_myplex_updateFriend(account, plex, mocker, shared_username):
    vid_filter = {"contentRating": ["G"], "label": ["foo"]}
    secs = plex.library.sections()
    user = account.user(shared_username)

    ids = account._getSectionIds(plex.machineIdentifier, secs)
    mocker.patch.object(account, "_getSectionIds", return_value=ids)
    mocker.patch.object(account, "user", return_value=user)
    with utils.callable_http_patch():
        account.updateFriend(
            shared_username,
            plex,
            secs,
            allowSync=True,
            removeSections=True,
            allowCameraUpload=True,
            allowChannels=False,
            filterMovies=vid_filter,
            filterTelevision=vid_filter,
            filterMusic={"label": ["foo"]},
        )

        with utils.callable_http_patch():
            account.removeFriend(shared_username)


def test_myplex_createExistingUser(account, plex, shared_username):
    user = account.user(shared_username)
    url = "https://plex.tv/api/invites/requested/{}?friend=0&server=0&home=1".format(
        user.id
    )

    account.createExistingUser(user, plex)
    assert shared_username in [u.username for u in account.users() if u.home is True]
    # Remove Home invite
    account.query(url, account._session.delete)
    # Confirm user was removed from home and has returned to friend
    assert shared_username not in [
        u.username for u in plex.myPlexAccount().users() if u.home is True
    ]
    assert shared_username in [
        u.username for u in plex.myPlexAccount().users() if u.home is False
    ]


@pytest.mark.skip(reason="broken test?")
def test_myplex_createHomeUser_remove(account, plex):
    homeuser = "New Home User"
    account.createHomeUser(homeuser, plex)
    assert homeuser in [u.title for u in plex.myPlexAccount().users() if u.home is True]
    account.removeHomeUser(homeuser)
    assert homeuser not in [
        u.title for u in plex.myPlexAccount().users() if u.home is True
    ]


def test_myplex_plexpass_attributes(account_plexpass):
    assert account_plexpass.subscriptionActive
    assert account_plexpass.subscriptionStatus == "Active"
    assert account_plexpass.subscriptionPlan
    assert "sync" in account_plexpass.subscriptionFeatures
    assert "premium_music_metadata" in account_plexpass.subscriptionFeatures
    assert "plexpass" in account_plexpass.roles
    assert utils.ENTITLEMENTS <= set(account_plexpass.entitlements)


def test_myplex_claimToken(account):
    assert account.claimToken().startswith("claim-")


def test_myplex_watchlist(account, movie, show, artist):
    assert not account.watchlist()

    # Add to watchlist from account
    account.addToWatchlist(movie)
    assert account.onWatchlist(movie)

    # Add to watchlist from object
    show.addToWatchlist(account)
    assert show.onWatchlist(account)

    # Remove from watchlist from account
    account.removeFromWatchlist(show)
    assert not account.onWatchlist(show)

    # Remove from watchlist from object
    movie.removeFromWatchlist(account)
    assert not movie.onWatchlist(account)

    # Add multiple items to watchlist
    account.addToWatchlist([movie, show])
    assert movie.onWatchlist(account) and show.onWatchlist(account)

    # Filter and sort watchlist
    watchlist = account.watchlist(filter='released', sort='titleSort', libtype='movie')
    guids = [i.guid for i in watchlist]
    assert movie.guid in guids and show.guid not in guids

    # Test adding existing item to watchlist
    with pytest.raises(BadRequest):
        account.addToWatchlist(movie)

    # Remove multiple items from watchlist
    account.removeFromWatchlist([movie, show])
    assert not movie.onWatchlist(account) and not show.onWatchlist(account)

    # Test removing non-existing item from watchlist
    with pytest.raises(BadRequest):
        account.removeFromWatchlist(movie)

    # Test adding invalid item to watchlist
    with pytest.raises(BadRequest):
        account.addToWatchlist(artist)
